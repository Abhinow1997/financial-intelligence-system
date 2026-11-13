# Airflow image

This folder builds the Docker image that every Airflow container runs. Airflow itself is
started by [`docker-compose-airflow.yaml`](../docker-compose-airflow.yaml) at the repo root.

| Path | What it is |
|---|---|
| [`airflow/Dockerfile`](Dockerfile) | Official `apache/airflow:3.3.2` + `requirements.txt`, tagged `fis-airflow:latest` |
| [`airflow/requirements.txt`](requirements.txt) | Python packages the DAGs import (e.g. `yfinance`) |
| [`docker-compose-airflow.yaml`](../docker-compose-airflow.yaml) | Runs Airflow: apiserver, scheduler, dag-processor, triggerer, worker, Postgres, Redis |
| [`dags/`](../dags) | All DAGs. Mounted live, so edits show up in about 30 s with no rebuild |

## Up and down

One-time setup: create `.env` with a `FERNET_KEY` (see
[the runbook](../docs/runbooks/airflow_local.md), step 1). Then, from the repo root:

```bash
docker compose -f docker-compose-airflow.yaml up -d --build
```

UI: http://localhost:8088, username `airflow`, password `airflow`. The first start takes 3–5 minutes.

```bash
docker compose -f docker-compose-airflow.yaml down
```

`down` keeps the run history. With `make`, the same commands are `make airflow-up` and `make airflow-down`.

## Add a dependency

1. **Python package:** add it to [`requirements.txt`](requirements.txt), with a version.
2. **System (apt) package:** uncomment the template in the [`Dockerfile`](Dockerfile).
3. Run the `up` command again. `--build` rebuilds the image.

DAG changes never need a rebuild; package changes always do.
