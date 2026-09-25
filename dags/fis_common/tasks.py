"""Reusable tasks for the `fis_backend_*` DAGs."""

from __future__ import annotations

from airflow.sdk import PokeReturnValue, task

from fis_common import backend_client


# `mode="reschedule"` frees the worker slot between pokes instead of sleeping in
# it, so a backend that is down for ten minutes doesn't pin a Celery worker for
# ten minutes. `timeout` bounds the total wait; after that the DAG run fails.
@task.sensor(poke_interval=30, timeout=10 * 60, mode="reschedule")
def wait_for_backend() -> PokeReturnValue:
    """Gate the DAG on `GET /health` so a stopped backend doesn't burn retries."""
    return PokeReturnValue(is_done=backend_client.is_healthy())
