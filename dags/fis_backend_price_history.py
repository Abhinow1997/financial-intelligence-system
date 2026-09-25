"""
### Daily OHLCV ingest via the FIS backend

Calls `GET /market/history/{ticker}` on the backend for each ticker, lands one CSV
per ticker per day in the raw zone, then runs data-quality checks over what landed.

    wait_for_backend -> list_tickers -> fetch_history[ticker] (mapped) -> validate -> summarize

What this DAG shows, beyond `market_daily_snapshot`:

* **Airflow as a client of your own API.** The DAG never imports yfinance; the
  backend owns the upstream. See `fis_common/backend_client.py` for how HTTP
  status codes map onto retry vs. fail-fast.
* **A sensor gate.** `wait_for_backend` polls `/health` in reschedule mode, so a
  stopped backend makes the run wait, not fail.
* **Files, not XCom, for data.** Each mapped task writes its bars to disk and
  returns only the path and row count. XCom lives in the metadata DB.
* **A separate data-quality task.** Validation reads the landed files and fails
  the run on bad data, so a silent upstream change can't reach downstream consumers.

Output: `data/raw/market_history/<date>/<TICKER>.csv`
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

RAW_DIR = Path("/opt/airflow/data/raw/market_history")

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "^GSPC"]


def _run_date() -> str:
    context = get_current_context()
    # Manually triggered Airflow 3 runs can have a null logical_date.
    return (context["logical_date"] or context["dag_run"].run_after).date().isoformat()


@dag(
    dag_id="fis_backend_price_history",
    # Weekdays 22:30 UTC - after the US close and after market_daily_snapshot.
    schedule="30 22 * * 1-5",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=1),
        "retry_exponential_backoff": True,
    },
    tags=["fis", "backend", "market-data", "ingest"],
    doc_md=__doc__,
    params={
        "tickers": DEFAULT_TICKERS,
        # Must be values the backend's `Period` / `Interval` enums accept, or the
        # backend returns 422 and the task fails without retrying.
        "period": "5d",
        "interval": "1d",
    },
)
def fis_backend_price_history():
    @task
    def list_tickers() -> list[str]:
        return [t.upper() for t in get_current_context()["params"]["tickers"]]

    # Four at a time: enough parallelism to be useful, few enough that the backend
    # doesn't fan out a burst to Yahoo and get us rate-limited.
    @task(max_active_tis_per_dagrun=4)
    def fetch_history(ticker: str) -> dict:
        params = get_current_context()["params"]
        payload = backend_client.get_history(ticker, params["period"], params["interval"])

        frame = pd.DataFrame(payload["bars"])
        frame.insert(0, "ticker", payload["ticker"])

        # Keyed by run date and ticker => re-running a day overwrites, never appends.
        # `^GSPC` is a legal filename on Linux but awkward on Windows hosts.
        destination = RAW_DIR / _run_date() / f"{ticker.replace('^', 'IDX_')}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(destination, index=False)

        log.info("%s: %d bars -> %s (backend %d ms)", ticker, len(frame), destination, payload["latency_ms"])
        return {"ticker": ticker, "path": str(destination), "rows": len(frame)}

    @task
    def validate(landed: list[dict]) -> list[dict]:
        """Fail the run if any landed file is empty or has impossible prices."""
        problems: list[str] = []
        for item in landed:
            frame = pd.read_csv(item["path"])
            ticker = item["ticker"]
            if frame.empty:
                problems.append(f"{ticker}: no rows")
                continue
            if frame[["open", "high", "low", "close"]].isna().any().any():
                problems.append(f"{ticker}: null prices")
            if (frame[["open", "high", "low", "close"]] <= 0).any().any():
                problems.append(f"{ticker}: non-positive prices")
            if (frame["high"] < frame["low"]).any():
                problems.append(f"{ticker}: high < low")
            if frame["timestamp"].duplicated().any():
                problems.append(f"{ticker}: duplicate timestamps")

        if problems:
            # Bad data won't fix itself on retry.
            raise AirflowFailException("Data-quality checks failed:\n" + "\n".join(problems))
        log.info("All %d files passed data-quality checks", len(landed))
        return landed

    @task
    def summarize(landed: list[dict]) -> dict:
        summary = {
            "date": _run_date(),
            "tickers": len(landed),
            "rows": sum(item["rows"] for item in landed),
        }
        log.info("Ingest summary: %s", summary)
        return summary

    tickers = list_tickers()
    wait_for_backend() >> tickers
    summarize(validate(fetch_history.expand(ticker=tickers)))


fis_backend_price_history()
