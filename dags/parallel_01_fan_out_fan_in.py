"""
### Parallel 1: fan-out / fan-in

The simplest kind of parallelism. `start` runs first, then three independent
fetch tasks run **at the same time**, then `combine` waits for all three.

```
start ─┬─► fetch_prices ──┐
       ├─► fetch_news ────┼─► combine
       └─► fetch_filings ─┘
```

Each fetch takes 5 seconds. One after another that would be 15 s; in parallel
it's about 5 s. Open the run in the Grid view and compare the start times of the
three fetch tasks: they start together.

Nothing special makes them parallel. None of the three depends on another, so
Airflow starts all of them as soon as `start` is done (up to the worker's
concurrency limit). The data is made up, so no network access is needed.
"""

from __future__ import annotations

import logging
import time

import pendulum
from airflow.sdk import dag, task

log = logging.getLogger(__name__)

# Long enough to see the tasks overlap in the UI.
WORK_SECONDS = 5

PRICES = {"AAPL": 231.40, "MSFT": 512.10, "NVDA": 186.75}
HEADLINES = {"AAPL": 12, "MSFT": 9, "NVDA": 21}
FILINGS = {"AAPL": 2, "MSFT": 1, "NVDA": 3}


@dag(
    dag_id="parallel_01_fan_out_fan_in",
    schedule=None,  # manual only: trigger it from the UI
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["lab", "parallel"],
    doc_md=__doc__,
)
def parallel_01_fan_out_fan_in():
    @task
    def start() -> list[str]:
        return list(PRICES)

    @task
    def fetch_prices(tickers: list[str]) -> dict[str, float]:
        time.sleep(WORK_SECONDS)
        return {t: PRICES[t] for t in tickers}

    @task
    def fetch_news(tickers: list[str]) -> dict[str, int]:
        time.sleep(WORK_SECONDS)
        return {t: HEADLINES[t] for t in tickers}

    @task
    def fetch_filings(tickers: list[str]) -> dict[str, int]:
        time.sleep(WORK_SECONDS)
        return {t: FILINGS[t] for t in tickers}

    @task
    def combine(prices: dict, headlines: dict, filings: dict) -> None:
        for t in prices:
            log.info(
                "%-5s price=%8.2f  headlines=%3d  filings=%d",
                t,
                prices[t],
                headlines[t],
                filings[t],
            )

    # Fan out: all three fetches take the same input, so they run side by side.
    # Fan in: combine needs all three outputs, so it waits for the slowest.
    tickers = start()
    combine(fetch_prices(tickers), fetch_news(tickers), fetch_filings(tickers))


parallel_01_fan_out_fan_in()
