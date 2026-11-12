# Airflow lab

A single-container Apache Airflow 3.3.2 for learning, with one example DAG.

| Path | What it is |
|---|---|
| [`Dockerfile`](Dockerfile) | Official `apache/airflow:3.3.2` image + your requirements + your DAGs, running `airflow standalone` |
| [`docker-compose.yaml`](docker-compose.yaml) | Builds the image and mounts `dags/` so edits show up without a rebuild |
| [`requirements.txt`](requirements.txt) | Extra Python packages your DAGs import (empty to start) |
| [`dags/hello_airflow.py`](dags/hello_airflow.py) | Example DAG: `say_hello` → `extract` → `transform` → `load` |

> This is separate from the repo's full Airflow stack ([`docker-compose-airflow.yaml`](../docker-compose-airflow.yaml),
> Celery + Postgres + Redis, see [`docs/runbooks/airflow_local.md`](../docs/runbooks/airflow_local.md)).
> The lab uses `airflow standalone` instead: one container, a SQLite metadata DB and the LocalExecutor.
> It's simpler to run, but its history is lost when the container is removed.

## Run it

You need Docker Desktop running with at least 4 GB of memory. From this folder:

```bash
docker compose up --build
```

The first build pulls about 1.2 GB. Airflow is ready once `docker compose ps` shows the container
as `(healthy)`, usually 30–60 seconds after it starts. To keep your terminal free, add `-d`.

**UI:** http://localhost:8089. There's no login: the image sets
`AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True`, and the port is bound to `127.0.0.1` only.
To use another port, set `AIRFLOW_LAB_PORT` (for example `AIRFLOW_LAB_PORT=8090 docker compose up`).

Stop it with `Ctrl+C`, or `docker compose down` to remove the container, which also wipes its SQLite DB.

## Run the example DAG

In the UI, open **hello_airflow**, unpause it with the toggle, then click **Trigger**. Open a task
and choose **Logs** to see its output.

Or from a second terminal:

```bash
docker compose exec airflow airflow dags test hello_airflow
```

`dags test` runs the whole DAG once in the foreground and prints every task's log. It's the fastest
way to debug a DAG, and it doesn't need the DAG unpaused.

## Add your own DAG

1. Create a `.py` file in [`dags/`](dags). The folder is mounted into the container, and the
   dag-processor picks it up within about 30 seconds.
2. If it fails to appear, check for import errors:
   ```bash
   docker compose exec airflow airflow dags list-import-errors
   ```
3. If it imports a new package, add the package to `requirements.txt` and run `docker compose up --build`.

## Useful commands

```bash
docker compose exec airflow airflow dags list
docker compose exec airflow airflow tasks list hello_airflow
docker compose exec airflow airflow tasks test hello_airflow extract 2026-01-01
docker compose logs -f airflow
```
