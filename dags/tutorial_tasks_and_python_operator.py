"""
### Tutorial: tasks and PythonOperator

A minimal, self-contained DAG (no backend, no network) that explains the basics:

* A **DAG** is the workflow: a set of tasks plus the order they run in.
* A **task** is one unit of work. Each task runs as its own process, can succeed,
  fail and retry on its own, and shows up as one box in the Graph view.
* An **operator** is a template for a task. `PythonOperator` runs a Python
  function you give it.
* **XCom** passes small values between tasks. A function's return value is pushed
  to XCom automatically.

The same work is written two ways so you can compare them:

    Classic PythonOperator:   say_hello -> make_prices -> average_price
    TaskFlow (@task):         make_prices_tf -> average_price_tf

Trigger it from the UI and open each task's *Logs* and *XCom* tabs.
"""

from __future__ import annotations

import logging

import pendulum
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import dag, task

log = logging.getLogger(__name__)


# --- Plain Python functions: these know nothing about Airflow. ---------------

def say_hello(name: str) -> None:
    # Anything logged here shows up in the task's Logs tab.
    log.info("Hello, %s! This is running inside an Airflow task.", name)


def make_prices() -> list[float]:
    # Returning a value pushes it to XCom under the key "return_value".
    return [101.5, 99.25, 103.0, 100.75]


def average_price(ti) -> float:
    # `ti` (task instance) is injected by Airflow because the parameter has that
    # name. Use it to pull the upstream task's return value out of XCom.
    prices = ti.xcom_pull(task_ids="make_prices")
    avg = sum(prices) / len(prices)
    log.info("Average of %s = %.2f", prices, avg)
    return avg


@dag(
    dag_id="tutorial_tasks_and_python_operator",
    schedule=None,  # manual trigger only
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["tutorial"],
    doc_md=__doc__,
)
def tutorial_tasks_and_python_operator():
    # --- Style 1: classic PythonOperator -------------------------------------
    # Each operator instance becomes one task. `task_id` must be unique in the DAG.
    hello = PythonOperator(
        task_id="say_hello",
        python_callable=say_hello,
        op_kwargs={"name": "FIS team"},  # arguments passed to the function
    )

    prices = PythonOperator(
        task_id="make_prices",
        python_callable=make_prices,
    )

    average = PythonOperator(
        task_id="average_price",
        python_callable=average_price,
        retries=2,  # per-task setting: only this task retries if it fails
    )

    # `>>` sets order: say_hello, then make_prices, then average_price.
    hello >> prices >> average

    # --- Style 2: TaskFlow (@task) -------------------------------------------
    # `@task` wraps a function in a PythonOperator for you. Passing one task's
    # output into another both moves the value through XCom and sets the order,
    # so no `>>` or `xcom_pull` is needed.
    @task
    def make_prices_tf() -> list[float]:
        return make_prices()

    @task
    def average_price_tf(values: list[float]) -> float:
        avg = sum(values) / len(values)
        log.info("TaskFlow average of %s = %.2f", values, avg)
        return avg

    average_price_tf(make_prices_tf())


tutorial_tasks_and_python_operator()
