"""
### Parallel 3: task groups running side by side

Each region is a small pipeline of its own: extract, then clean, then load. Each
pipeline is wrapped in a TaskGroup. The regions don't depend on each other, so the
three pipelines run **in parallel**, while the steps inside each one still run in
order.

```
         ┌─ us:   extract → clean → load ─┐
start ───┼─ eu:   extract → clean → load ─┼─► report
         └─ asia: extract → clean → load ─┘
```

Each pipeline has two 5-second steps. One region after another would take over
30 s; in parallel the whole run takes about 15 s. In the Graph view, click a group
to expand or collapse it.
"""

from __future__ import annotations

import logging
import time

import pendulum
from airflow.sdk import TaskGroup, dag, task

log = logging.getLogger(__name__)

WORK_SECONDS = 5

REGIONS = {
    "us": ["NYSE", "NASDAQ"],
    "eu": ["LSE", "Euronext", "Xetra"],
    "asia": ["TSE", "HKEX"],
}


@dag(
    dag_id="parallel_03_task_groups",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["lab", "parallel"],
    doc_md=__doc__,
)
def parallel_03_task_groups():
    @task
    def start() -> None:
        log.info(
            "Processing %d regions in parallel: %s", len(REGIONS), ", ".join(REGIONS)
        )

    @task
    def extract(region: str) -> list[dict]:
        time.sleep(WORK_SECONDS)
        exchanges = REGIONS[region]
        return [
            {"exchange": ex, "trades": 1000 * (i + 1)} for i, ex in enumerate(exchanges)
        ]

    @task
    def clean(rows: list[dict]) -> list[dict]:
        time.sleep(WORK_SECONDS)
        return [r for r in rows if r["trades"] > 0]

    @task
    def load(region: str, rows: list[dict]) -> dict:
        total = sum(r["trades"] for r in rows)
        log.info("Loaded %d exchanges for %s (%d trades)", len(rows), region, total)
        return {"region": region, "exchanges": len(rows), "trades": total}

    @task
    def report(results: list[dict]) -> None:
        for r in results:
            log.info(
                "%-4s %d exchanges, %6d trades",
                r["region"],
                r["exchanges"],
                r["trades"],
            )
        log.info("Total trades: %d", sum(r["trades"] for r in results))

    begin = start()
    results = []
    for region in REGIONS:
        # Tasks created inside this block get the group's name as a prefix
        # (us.extract, eu.extract, ...), so one task definition serves every region.
        with TaskGroup(group_id=region) as group:
            results.append(load(region, clean(extract(region))))
        begin >> group

    # A list of outputs from different tasks: report waits for all of them.
    report(results)


parallel_03_task_groups()
