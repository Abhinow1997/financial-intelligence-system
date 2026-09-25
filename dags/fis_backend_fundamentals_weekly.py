"""
### Weekly fundamentals snapshot + value screen via the FIS backend

Calls `GET /market/fundamentals/{ticker}` for a watchlist, writes one table per
week, and flags names that pass a simple value screen.

    wait_for_backend -> list_tickers -> fetch_fundamentals[ticker] (mapped) -> build_table -> screen

What this DAG shows:

* **Throttling an expensive call.** `/market/fundamentals` hits yfinance's heavy
  `.info` endpoint, the one Yahoo rate-limits hardest. The mapped task runs one
  at a time (`max_active_tis_per_dagrun=1`) with a long retry delay.
* **Partial success with `trigger_rule`.** One delisted ticker shouldn't sink the
  whole weekly table. `build_table` runs with `all_done` and uses whatever
  succeeded; `screen` then fails the run only if *nothing* came back.
* **Weekly cadence, dated output.** Files are keyed by the run date, so re-running
  a week replaces its snapshot.

Output: `data/processed/fundamentals/<date>.csv` and `<date>_screen.csv`
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pendulum
from airflow.sdk import dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

from fis_common import backend_client
from fis_common.tasks import wait_for_backend

log = logging.getLogger(__name__)

OUT_DIR = Path("/opt/airflow/data/processed/fundamentals")

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM", "KO", "JNJ"]

# Columns kept in the table. `summary` (long business description) is dropped to
# keep the CSV readable.
COLUMNS = [
    "ticker", "name", "sector", "industry", "market_cap", "trailing_pe", "forward_pe",
    "trailing_eps", "dividend_yield", "beta", "week52_high", "week52_low",
]


def _run_date() -> str:
    context = get_current_context()
    return (context["logical_date"] or context["dag_run"].run_after).date().isoformat()


@dag(
    dag_id="fis_backend_fundamentals_weekly",
    # Saturdays 12:00 UTC - fundamentals move slowly and markets are closed.
    schedule="0 12 * * 6",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=3),
        "retry_exponential_backoff": True,
    },
    tags=["fis", "backend", "fundamentals", "screen"],
    doc_md=__doc__,
    params={
        "tickers": DEFAULT_TICKERS,
        "max_forward_pe": 25.0,
        "min_dividend_yield": 0.5,
    },
)
def fis_backend_fundamentals_weekly():
    @task
    def list_tickers() -> list[str]:
        return [t.upper() for t in get_current_context()["params"]["tickers"]]

    @task(max_active_tis_per_dagrun=1)
    def fetch_fundamentals(ticker: str) -> dict:
        payload = backend_client.get_fundamentals(ticker)
        log.info("%s: %s (backend %d ms)", ticker, payload.get("name"), payload["latency_ms"])
        # Small, flat dict - fine for XCom.
        return {column: payload.get(column) for column in COLUMNS}

    # `all_done`: run even if some mapped fetches failed. Failed map indexes simply
    # contribute nothing to `rows`.
    @task(trigger_rule="all_done")
    def build_table(rows: list[dict]) -> str | None:
        rows = [row for row in rows if row]
        if not rows:
            return None
        frame = pd.DataFrame(rows, columns=COLUMNS).sort_values("market_cap", ascending=False)
        destination = OUT_DIR / f"{_run_date()}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(destination, index=False)
        log.info("Wrote %d companies to %s", len(frame), destination)
        return str(destination)

    @task
    def screen(table_path: str | None) -> list[str]:
        """Simple value screen: reasonable forward P/E and a real dividend."""
        if table_path is None:
            raise AirflowFailException("No fundamentals fetched for any ticker.")

        params = get_current_context()["params"]
        frame = pd.read_csv(table_path)
        passed = frame[
            (frame["forward_pe"] > 0)
            & (frame["forward_pe"] <= params["max_forward_pe"])
            # yfinance reports dividendYield in percent (0.41 == 0.41%).
            & (frame["dividend_yield"] >= params["min_dividend_yield"])
        ]

        destination = Path(table_path).with_name(Path(table_path).stem + "_screen.csv")
        passed.to_csv(destination, index=False)
        log.info(
            "%d of %d passed (fwd P/E <= %s, yield >= %s%%): %s",
            len(passed), len(frame), params["max_forward_pe"], params["min_dividend_yield"],
            passed["ticker"].tolist(),
        )
        return passed["ticker"].tolist()

    tickers = list_tickers()
    wait_for_backend() >> tickers
    screen(build_table(fetch_fundamentals.expand(ticker=tickers)))


fis_backend_fundamentals_weekly()
