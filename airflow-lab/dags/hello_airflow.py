"""
### Hello Airflow

A minimal extract -> transform -> load DAG for the Airflow lab. The data is a
hard-coded list of card transactions, so the DAG needs no network or credentials.

What to look for:

* **Two ways to write a task**: a classic operator (`BashOperator`) and the
  TaskFlow API (`@task`-decorated Python functions).
* **Dependencies**: `>>` sets order explicitly; passing one task's return value
  into another sets it implicitly.
* **XCom**: return values travel between tasks through the metadata database.
  Keep them small (a list of dicts, a path), never a whole DataFrame.
* **Templating**: `{{ run_id }}` in the bash command is filled in at run time.

Requires Airflow 3.x (uses `airflow.sdk`).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task

log = logging.getLogger(__name__)


@dag(
    dag_id="hello_airflow",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    # Without this, unpausing the DAG would immediately backfill one run per day
    # since start_date.
    catchup=False,
    default_args={
        "owner": "airflow-lab",
        "retries": 1,
        "retry_delay": timedelta(seconds=30),
    },
    tags=["lab", "airflow-lab"],
    doc_md=__doc__,
)
def hello_airflow():
    say_hello = BashOperator(
        task_id="say_hello",
        bash_command='echo "Hello from Airflow! dag={{ dag.dag_id }} run={{ run_id }}"',
    )

    @task
    def extract() -> list[dict]:
        """Pretend to pull today's transactions from a source system."""
        rows = [
            {"txn_id": 1, "category": "groceries", "amount": 82.40},
            {"txn_id": 2, "category": "transport", "amount": 15.00},
            {"txn_id": 3, "category": "groceries", "amount": 41.15},
            {"txn_id": 4, "category": "dining", "amount": 63.90},
            {"txn_id": 5, "category": "transport", "amount": 9.75},
        ]
        log.info("Extracted %d transactions", len(rows))
        return rows

    @task
    def transform(rows: list[dict]) -> dict:
        """Total spend per category."""
        totals: dict[str, float] = {}
        for row in rows:
            category = row["category"]
            totals[category] = round(totals.get(category, 0.0) + row["amount"], 2)
        return {
            "transactions": len(rows),
            "total_spend": round(sum(totals.values()), 2),
            "by_category": totals,
        }

    @task
    def load(summary: dict) -> None:
        """Pretend to write the summary to a warehouse; here we just log it."""
        log.info(
            "Processed %d transactions, total spend %.2f",
            summary["transactions"],
            summary["total_spend"],
        )
        for category, amount in sorted(summary["by_category"].items()):
            log.info("  %-10s %8.2f", category, amount)

    rows = extract()
    say_hello >> rows
    load(transform(rows))


hello_airflow()
