"""
### Parallel 4: keep going when one parallel task fails

Three data vendors are queried in parallel. By default, if one of them fails,
every task downstream is marked `upstream_failed` and nothing is produced. Here
`merge` uses `trigger_rule="all_done"`: it runs once every vendor has **finished**,
whether it succeeded or failed, and merges whatever came back.

```
┌─► vendor_a ─┐
├─► vendor_b ─┼─► merge   (trigger_rule="all_done")
└─► vendor_c ─┘
```

**Try it:** trigger with `{"fail_vendor": "vendor_b"}`. `vendor_b` fails, and
`merge` still runs and averages the quotes from `vendor_a` and `vendor_c`.

`merge` reads the vendors' results with `xcom_pull` instead of taking them as
arguments. A failed vendor has no result, and `xcom_pull` simply returns `None`
for it.

**Gotcha:** that run is marked **success** even though `vendor_b` failed. A run's
final state comes from its last tasks, here `merge`. If losing a vendor should
fail the run, make `merge` raise when too few vendors answered.
"""

from __future__ import annotations

import logging
import time

import pendulum
from airflow.sdk import dag, get_current_context, task

log = logging.getLogger(__name__)

WORK_SECONDS = 5

VENDORS = {
    "vendor_a": {"AAPL": 231.40, "MSFT": 512.10},
    "vendor_b": {"AAPL": 231.38, "NVDA": 186.75},
    "vendor_c": {"MSFT": 512.15, "NVDA": 186.70},
}


@dag(
    dag_id="parallel_04_partial_failure",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    # No retries, so the requested failure shows up straight away.
    default_args={"retries": 0},
    tags=["lab", "parallel"],
    doc_md=__doc__,
    params={"fail_vendor": ""},
)
def parallel_04_partial_failure():
    @task
    def fetch(vendor: str) -> dict[str, float]:
        time.sleep(WORK_SECONDS)
        if get_current_context()["params"]["fail_vendor"] == vendor:
            raise RuntimeError(
                f"{vendor} returned HTTP 503 (failure requested via params)"
            )
        return VENDORS[vendor]

    # all_done: run once every upstream task has finished, success OR failure.
    # The default, all_success, would skip merge as soon as one vendor failed.
    @task(trigger_rule="all_done")
    def merge() -> dict[str, float]:
        ti = get_current_context()["ti"]
        quotes: dict[str, list[float]] = {}
        for vendor in VENDORS:
            data = ti.xcom_pull(task_ids=vendor)
            if data is None:
                log.warning("No data from %s, merging without it", vendor)
                continue
            for ticker, price in data.items():
                quotes.setdefault(ticker, []).append(price)
        merged = {t: round(sum(p) / len(p), 2) for t, p in quotes.items()}
        log.info("Merged quotes from the vendors that answered: %s", merged)
        return merged

    # One task definition, three tasks: .override() gives each its own task_id.
    fetches = [fetch.override(task_id=vendor)(vendor) for vendor in VENDORS]
    fetches >> merge()


parallel_04_partial_failure()
