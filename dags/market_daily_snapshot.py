"""
### Daily market snapshot

Pulls a closing-price snapshot for the tickers on the watchlist from Yahoo Finance,
ranks them by daily return, and writes one JSON report per run into the shared data lake.

**Which tickers** (the first one that's set wins):

1. `tickers` in the run's config, for a one-off manual run, e.g. `{"tickers": ["AAPL"]}`.
2. The Variable `watchlist_tickers` (**Admin → Variables**), e.g. `AAPL,MSFT,NVDA,AMZN`
   or `["AAPL", "MSFT"]`. The scheduled daily run uses this, and so does
   `parallel_02_dynamic_mapping`: change the watchlist once and both DAGs follow it.
3. `DEFAULT_TICKERS` in this file, if neither of the above is set.

This is the "why a scheduler and not a `for` loop" demo for the course. The work
itself is trivial; what Airflow adds is:

* **one task per ticker** (`.expand()`), so every symbol on the watchlist is
  fetched in parallel across Celery workers instead of serially. Add a ticker to
  the Variable and the next run has one more parallel task, with no code change;
* **a retry boundary per ticker** — a rate-limited `NVDA` retries on its own and
  does not re-fetch the three symbols that already succeeded;
* **a distinction between retryable and permanent failure** — a throttled request
  backs off, a nonexistent symbol fails immediately instead of burning three retries;
* **idempotency** — the output path is keyed by the run's date, so re-running a day
  overwrites that day rather than appending a duplicate.

Requires Airflow 3.x (uses `airflow.sdk`) and `yfinance>=1.7`.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pendulum
import yfinance as yf
from airflow.sdk.exceptions import AirflowFailException
from airflow.sdk import Param, Variable, dag, get_current_context, task
from yfinance.exceptions import YFRateLimitError

log = logging.getLogger(__name__)

# Bind-mounted from ./data in docker-compose-airflow.yaml, so you can read the
# output from the host. `data/processed/*` is gitignored.
OUTPUT_DIR = Path("/opt/airflow/data/processed/market_snapshots")

VARIABLE_KEY = "watchlist_tickers"
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]


def parse_tickers(raw: str) -> list[str]:
    """Accept a JSON list (["AAPL", "MSFT"]) or a comma-separated string (AAPL,MSFT)."""
    raw = raw.strip()
    items = json.loads(raw) if raw.startswith("[") else raw.split(",")
    return [str(t).strip().upper() for t in items if str(t).strip()]


@dag(
    dag_id="market_daily_snapshot",
    # Weekdays at 22:00 UTC, comfortably after the US close.
    schedule="0 22 * * 1-5",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    # Without this, Airflow would immediately backfill every weekday since
    # start_date the moment you unpause the DAG.
    catchup=False,
    max_active_runs=1,
    default_args={
        # Yahoo throttles. Retry with a gap rather than hammering it.
        "retries": 3,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
    },
    tags=["lab", "market-data", "yfinance"],
    doc_md=__doc__,
    params={
        "tickers": Param(
            [],
            type="array",
            description=(
                "Optional: tickers for this run only. "
                f"Leave empty to use the {VARIABLE_KEY} Variable."
            ),
        )
    },
)
def market_daily_snapshot():
    @task
    def list_tickers() -> list[str]:
        """Decide which tickers this run fetches: run config, then Variable, then default.

        Its return value drives `.expand()` below, so the length of this list is
        the number of parallel `fetch_one` tasks. The Variable is read here, at run
        time, not at the top of the file: top-level code runs every time Airflow
        parses the file (about every 30 s), even when nothing is running.
        """
        override = get_current_context()["params"]["tickers"]
        if override:
            tickers, source = [str(t).upper() for t in override], "run config"
        else:
            raw = Variable.get(VARIABLE_KEY, default=None)
            if raw:
                tickers, source = parse_tickers(raw), f"Variable {VARIABLE_KEY}"
            else:
                tickers, source = DEFAULT_TICKERS, "DEFAULT_TICKERS (Variable not set)"

        if not tickers:
            raise AirflowFailException(f"{source} gave an empty ticker list.")
        log.info("Fetching %d symbols from %s: %s", len(tickers), source, tickers)
        return tickers

    @task
    def fetch_one(ticker: str) -> dict:
        """Fetch one symbol. This is the unit of parallelism *and* of retry."""
        try:
            frame = yf.Ticker(ticker).history(period="5d", interval="1d")
        except YFRateLimitError as exc:
            # Transient: let the task fail normally so Airflow retries with backoff.
            raise RuntimeError(f"Yahoo rate-limited {ticker}; will retry") from exc

        if frame.empty:
            # Permanent: yfinance returns an empty frame rather than raising for an
            # unknown symbol. Retrying cannot fix a typo, so fail without retries.
            raise AirflowFailException(
                f"No data for '{ticker}' - unknown or delisted symbol."
            )

        closes = frame["Close"]
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else last

        return {
            "ticker": ticker,
            "close": round(last, 4),
            "previous_close": round(prev, 4),
            "change_pct": round((last - prev) / prev * 100, 4) if prev else 0.0,
            "volume": int(frame["Volume"].iloc[-1]),
            "as_of": closes.index[-1].date().isoformat(),
        }

    @task
    def summarize(rows: list[dict]) -> dict:
        """Collapse the mapped results into one ranked summary.

        `rows` arrives as the list of every `fetch_one` return value. Airflow passes
        these through XCom, which is backed by the metadata database - keep what
        crosses a task boundary small. A DataFrame belongs in object storage with
        only its path in XCom.
        """
        ranked = sorted(rows, key=lambda r: r["change_pct"], reverse=True)
        return {
            "count": len(ranked),
            "best": ranked[0]["ticker"],
            "worst": ranked[-1]["ticker"],
            "mean_change_pct": round(sum(r["change_pct"] for r in ranked) / len(ranked), 4),
            "rows": ranked,
        }

    @task
    def write_report(summary: dict) -> str:
        """Write one JSON file per run, named for the period the data covers."""
        context = get_current_context()
        # Manually triggered runs in Airflow 3 have no `logical_date`: the key is
        # missing from the context, not just None. So use .get() and fall back to
        # `run_after`, which is always set.
        stamp = (context.get("logical_date") or context["dag_run"].run_after).date()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # Same filename for the same date => re-running a day replaces it. That is
        # what makes this task safe to re-run, which is what makes backfill safe.
        destination = OUTPUT_DIR / f"{stamp.isoformat()}.json"
        destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        log.info(
            "Wrote %d rows to %s (best=%s, worst=%s)",
            summary["count"],
            destination,
            summary["best"],
            summary["worst"],
        )
        return str(destination)

    # `.expand()` is dynamic task mapping: one `fetch_one` task instance per ticker,
    # created at runtime from the upstream return value. The UI shows them as a
    # single mapped task you can drill into.
    quotes = fetch_one.expand(ticker=list_tickers())
    write_report(summarize(quotes))


market_daily_snapshot()
