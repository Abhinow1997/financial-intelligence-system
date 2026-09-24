# Running Airflow locally

Airflow ships as a **separate** compose file at the repo root,
[`docker-compose-airflow.yaml`](../../docker-compose-airflow.yaml) — the stock Apache
Airflow 3.3.2 `CeleryExecutor` bundle (apiserver, scheduler, dag-processor, triggerer,
worker, plus its own Postgres and Redis). It is not part of the main
[`docker-compose.yml`](../../docker-compose.yml) and does not share anything with it.

---

## 1. One-time setup

```bash
cp .env.example .env
```

Then generate a Fernet key and paste it into `.env` as `FERNET_KEY=`:

```bash
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

> **Why this is required.** The compose file reads `${FERNET_KEY}` with **no default**.
> Airflow uses it to encrypt connection passwords and variables at rest. Leave it blank
> and each container generates its own key on boot, so the scheduler cannot decrypt what
> the apiserver wrote — you get confusing `InvalidToken` errors instead of a clean failure.
> `.env` is gitignored; the key is a secret and must never be committed.

The four bind-mounted directories (`dags/`, `logs/`, `plugins/`, `config/`) are already
in the repo with `.gitkeep` files. Airflow's runtime output in them is gitignored.

**Docker resources:** Airflow wants ≥ 4 GB RAM and 2 CPUs. Check with `docker info`;
raise the limit in Docker Desktop → Settings → Resources if needed.

---

## 2. Start it

```bash
make airflow-up
```

or directly:

```bash
docker compose -p fis-airflow -f docker-compose-airflow.yaml up -d
```

> **`-p fis-airflow` is not optional.** Without it, Docker derives the project name from
> the directory — the same name the main stack uses. Both files define services called
> `postgres` and `redis`, so they would fight over the same container names, and a
> `docker compose down` on one file would tear down the other's containers. The name is
> `fis-airflow` rather than plain `airflow` so it also stays clear of any unrelated
> Airflow you already run on this machine. The `make` targets always pass it.

First run pulls ~2 GB of images and runs `airflow-init` (database migration + admin user),
so allow 3–5 minutes. Watch progress with:

```bash
make airflow-ps
```

Wait until `airflow-apiserver` reports `(healthy)`.

**UI:** http://localhost:8088 — username `airflow`, password `airflow`.

---

## 3. Port 8088, not 8080

Port 8080 is contested: this repo's `gateway` service wants it, and so does the default
Airflow webserver. The apiserver therefore publishes on **8088** by default:

```yaml
ports:
  - "${AIRFLOW_PORT:-8088}:8080"
```

Set `AIRFLOW_PORT` in `.env` to move it. Only the host side changes — inside the Docker
network the apiserver is still on 8080, which is what
`AIRFLOW__CORE__EXECUTION_API_SERVER_URL` points at. Do not change the container port.

With this default you can run the whole repo and Airflow side by side: `make up-core`
(gateway :8080, backend :8000, frontend :8501) plus `make airflow-up` (:8088).

---

## 4. Day-to-day

```bash
make airflow-ps                          # container health
make airflow-logs                        # tail scheduler + apiserver
make airflow-cli CMD="dags list"         # any Airflow CLI command
make airflow-cli CMD="dags test <id> 2026-01-01"
make airflow-down                        # stop, keep the metadata DB
make airflow-reset                       # stop and DELETE the metadata DB volume
```

Add DAGs as `.py` files in [`dags/`](../../dags). The dag-processor picks up changes
within about 30 seconds — no restart needed.

### The example DAG

[`dags/market_daily_snapshot.py`](../../dags/market_daily_snapshot.py) fetches closing
prices for four tickers, ranks them by daily return, and writes one JSON report per run
to `data/processed/market_snapshots/`. Unpause it in the UI, or:

```bash
make airflow-dag                                    # trigger one run
cat data/processed/market_snapshots/*.json          # read the output
```

It exists to show what a scheduler buys you over a `for` loop:

| Airflow feature | Where to look |
|---|---|
| Dynamic task mapping — one task per ticker, run in parallel | `fetch_one.expand(ticker=...)` |
| Per-item retry boundary — one throttled symbol doesn't re-fetch the others | `retries` in `default_args` |
| Retryable vs. permanent failure | `RuntimeError` on `YFRateLimitError` vs. `AirflowFailException` on an empty frame |
| Idempotent output, so re-runs and backfills are safe | filename keyed by the run's date in `write_report` |
| XCom for small values only | the docstring on `summarize` |
| `catchup=False` to avoid a surprise backfill | the `@dag` decorator |

**`yfinance` inside the containers.** The compose file installs it via
`_PIP_ADDITIONAL_REQUIREMENTS`, which re-runs `pip install` on *every* container start —
about 40 seconds × 6 containers. That is fine for a lab and terrible for anything else.
The real fix is a custom image: uncomment `build: .` in `x-airflow-common`, add a
`Dockerfile` with `FROM apache/airflow:3.3.2` + `RUN pip install yfinance>=1.7.0`, and
run `make airflow-up` — see
[Airflow's image docs](https://airflow.apache.org/docs/docker-stack/build.html).

The compose file sets `AIRFLOW__CORE__LOAD_EXAMPLES: 'true'`, so the UI starts full of
Apache's example DAGs. To hide them, flip that to `'false'` and run `make airflow-reset`
followed by `make airflow-up`.

---

## 5. Troubleshooting

- **`variable is not set` warning for `FERNET_KEY`** → you skipped step 1.
- **`unexpected EOF` / exit code 18 during the first pull** → the `apache/airflow` image is
  ~1.2 GB and the download dropped. Just run `make airflow-up` again; Docker keeps the
  layers it already fetched and resumes.
- **`airflow-init` exits non-zero** → almost always not enough memory. It prints an
  explicit `Not enough memory available for Docker` warning; read its logs with
  `docker compose -p airflow -f docker-compose-airflow.yaml logs airflow-init`.
- **`Bind for 0.0.0.0:8080 failed: port is already allocated`** → see §3.
- **Containers stuck `(health: starting)`** → normal for the first 60–90 s after
  `airflow-init` completes. Only worry after ~3 minutes.
- **`docker compose down` removed the wrong containers** → you omitted `-p airflow`.
- **Empty DAG list but your file is in `dags/`** → check for an import error under
  *Browse → DAG Import Errors* in the UI, or run `make airflow-cli CMD="dags list-import-errors"`.

---

## 6. Where this is heading

Right now Airflow is standalone scaffolding. The intended use is scheduling the ingestion
workers in [`services/ingestion/*`](../../services/ingestion) — the nightly market-data,
filings and news pulls — so the backend serves from a warm store instead of hitting Yahoo
on the request path. See [`ARCHITECTURE.md`](../../ARCHITECTURE.md).
