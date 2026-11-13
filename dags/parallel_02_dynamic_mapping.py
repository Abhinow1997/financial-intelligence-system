"""
### Parallel 2: dynamic task mapping, with the list from a Variable

Use this when you don't know how many parallel tasks you need until the DAG runs.
`.expand()` creates one task instance per item **at run time**. Here the list of
tickers comes from an Airflow **Variable**, so you can change it without touching
the code.

```
list_tickers ─► score [one copy per ticker, at most 3 at a time] ─► rank
```

**Where the tickers come from** (the first one that's set wins):

1. `tickers` in the run's config, for a one-off run. Trigger with
   `{"tickers": ["AAPL", "MSFT"]}`.
2. The Variable `watchlist_tickers`, the standing list every run uses. Set it in
   **Admin → Variables** to `AAPL,MSFT,NVDA` or `["AAPL", "MSFT", "NVDA"]`, or run
   `airflow variables set watchlist_tickers AAPL,MSFT,NVDA`.
3. The 8 tickers in `DEFAULT_TICKERS`, if neither of the above is set.

A **Variable** is a setting stored in Airflow: every run (and any DAG that reads it)
sees the same value, and you change it without editing code. A **param** is an
input to a single run.

How the mapping works:

- `.expand(ticker=...)` creates one copy of `score` per ticker.
- `.partial(window=20)` passes the same value to every copy.
- `max_active_tis_per_dag=3` caps how many copies run at once, for example to stay
  under an API's rate limit. With 8 tickers, the copies run in three waves (3, 3,
  then 2), about 20 s in all.
"""

from __future__ import annotations

import json
import logging
import time

import pendulum
from airflow.sdk import Param, Variable, dag, get_current_context, task

log = logging.getLogger(__name__)

WORK_SECONDS = 5

VARIABLE_KEY = "watchlist_tickers"
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM"]


def parse_tickers(raw: str) -> list[str]:
    """Accept a JSON list (["AAPL", "MSFT"]) or a comma-separated string (AAPL,MSFT)."""
    raw = raw.strip()
    items = json.loads(raw) if raw.startswith("[") else raw.split(",")
    return [str(t).strip().upper() for t in items if str(t).strip()]


@dag(
    dag_id="parallel_02_dynamic_mapping",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["lab", "parallel"],
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
def parallel_02_dynamic_mapping():
    @task
    def list_tickers() -> list[str]:
        # Read the Variable here, inside a task, so it's read once per run. At the
        # top of the file it would be read every time Airflow parses this file
        # (about every 30 s), even when nothing is running.
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
            raise ValueError(f"{source} gave an empty ticker list")
        log.info("Creating one score task per ticker from %s: %s", source, tickers)
        return tickers

    # At most 3 copies of this task run at once, across all runs of this DAG.
    @task(max_active_tis_per_dag=3)
    def score(ticker: str, window: int) -> dict:
        time.sleep(WORK_SECONDS)
        # A made-up but repeatable "momentum", so the demo needs no network.
        momentum = round(((sum(map(ord, ticker)) % 41) - 20) / 10, 2)
        return {"ticker": ticker, "window": window, "momentum": momentum}

    @task
    def rank(scores: list[dict]) -> None:
        # `scores` holds the return value of every mapped copy.
        ranked = sorted(scores, key=lambda s: s["momentum"], reverse=True)
        for position, s in enumerate(ranked, start=1):
            log.info(
                "%d. %-5s momentum %+.2f (%d-day window)",
                position,
                s["ticker"],
                s["momentum"],
                s["window"],
            )

    scores = score.partial(window=20).expand(ticker=list_tickers())
    rank(scores)


parallel_02_dynamic_mapping()
