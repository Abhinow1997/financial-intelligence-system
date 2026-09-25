"""
### Watchlist momentum signal via the FIS backend

Calls `POST /market/compare` once per lookback window (1mo, 3mo, 6mo), combines
the returns into a momentum score per ticker, and branches: if any ticker beats
the threshold on *every* window it writes a signal report, otherwise it records
a no-signal run.

    wait_for_backend -> check_watchlist -> compare_window[period] (mapped) -> score -> branch
                                                                                        |-> write_signal
                                                                                        '-> no_signal

What this DAG shows:

* **Mapping over a parameter other than ticker.** One task per lookback window,
  each a single POST covering the whole watchlist.
* **Validating inputs before calling the API.** The backend accepts 2-5 tickers.
  `check_watchlist` fails fast with a clear message instead of letting every
  mapped task burn its retries on a 422.
* **Branching with `@task.branch`.** Only one of `write_signal` / `no_signal`
  runs; the other shows as *skipped* in the grid.

Output: `data/processed/momentum/<date>.json` (signal runs only)
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

from fis_common import backend_client
from fis_common.tasks import wait_for_backend

log = logging.getLogger(__name__)

OUT_DIR = Path("/opt/airflow/data/processed/momentum")

# The backend's CompareRequest caps this at 5.
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
WINDOWS = ["1mo", "3mo", "6mo"]


@dag(
    dag_id="fis_backend_watchlist_momentum",
    # Weekdays 23:00 UTC, after the price-history ingest.
    schedule="0 23 * * 1-5",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
    },
    tags=["fis", "backend", "signals"],
    doc_md=__doc__,
    params={
        "watchlist": DEFAULT_WATCHLIST,
        # Minimum return (%) a ticker needs on EVERY window to count as a signal.
        "min_return_pct": 5.0,
    },
)
def fis_backend_watchlist_momentum():
    @task(retries=0)
    def check_watchlist() -> list[str]:
        tickers = [t.upper() for t in get_current_context()["params"]["watchlist"]]
        if not 2 <= len(tickers) <= 5:
            raise AirflowFailException(
                f"watchlist must have 2-5 tickers (backend limit), got {len(tickers)}: {tickers}"
            )
        return tickers

    @task
    def compare_window(period: str, tickers: list[str]) -> dict:
        payload = backend_client.compare(tickers, period)
        log.info("%s leader: %s (backend %d ms)", period, payload["best"], payload["latency_ms"])
        return {
            "period": period,
            "returns": {row["ticker"]: round(row["return_pct"], 2) for row in payload["results"]},
        }

    @task
    def score(windows: list[dict]) -> dict:
        """Momentum score = mean return across windows. Keeps the per-window detail."""
        by_ticker: dict[str, dict[str, float]] = {}
        for window in windows:
            for ticker, ret in window["returns"].items():
                by_ticker.setdefault(ticker, {})[window["period"]] = ret

        min_return = get_current_context()["params"]["min_return_pct"]
        scored = []
        for ticker, returns in by_ticker.items():
            scored.append(
                {
                    "ticker": ticker,
                    "returns_pct": returns,
                    "score": round(sum(returns.values()) / len(returns), 2),
                    "signal": all(ret >= min_return for ret in returns.values()),
                }
            )
        scored.sort(key=lambda row: row["score"], reverse=True)
        for row in scored:
            log.info("%-6s score=%7.2f signal=%s %s", row["ticker"], row["score"], row["signal"], row["returns_pct"])
        return {"min_return_pct": min_return, "ranking": scored}

    @task.branch
    def any_signal(scores: dict) -> str:
        # Return the task_id to follow; everything else directly downstream is skipped.
        return "write_signal" if any(row["signal"] for row in scores["ranking"]) else "no_signal"

    @task
    def write_signal(scores: dict) -> str:
        context = get_current_context()
        stamp = (context["logical_date"] or context["dag_run"].run_after).date().isoformat()
        leaders = [row["ticker"] for row in scores["ranking"] if row["signal"]]

        destination = OUT_DIR / f"{stamp}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"date": stamp, "leaders": leaders, **scores}, indent=2), encoding="utf-8")
        log.info("Momentum leaders %s -> %s", leaders, destination)
        return str(destination)

    @task
    def no_signal(scores: dict) -> None:
        log.info(
            "No ticker cleared %s%% on every window. Top score: %s",
            scores["min_return_pct"],
            scores["ranking"][0] if scores["ranking"] else None,
        )

    tickers = check_watchlist()
    wait_for_backend() >> tickers
    scores = score(compare_window.partial(tickers=tickers).expand(period=WINDOWS))
    any_signal(scores) >> [write_signal(scores), no_signal(scores)]


fis_backend_watchlist_momentum()
