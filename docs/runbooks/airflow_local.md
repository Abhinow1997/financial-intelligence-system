# Running Airflow locally

Airflow ships as a **separate** compose file at the repo root,
[`docker-compose-airflow.yaml`](../../docker-compose-airflow.yaml) — the stock Apache
Airflow 3.3.2 `CeleryExecutor` bundle (apiserver, scheduler, dag-processor, triggerer,
worker, plus its own Postgres and Redis). It is not part of the main
[`docker-compose.yml`](../../docker-compose.yml) and does not share anything with it.

Every Airflow container runs the repo's own image, built from
[`airflow/Dockerfile`](../../airflow/Dockerfile): the official image plus the packages in
[`airflow/requirements.txt`](../../airflow/requirements.txt).

**Start and stop**, after the one-time setup in §1:

```bash
docker compose -f docker-compose-airflow.yaml up -d --build
docker compose -f docker-compose-airflow.yaml down
```

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

or directly (no `make` needed):

```bash
docker compose -f docker-compose-airflow.yaml up -d --build
```

> **Why no `-p` flag?** The compose file sets `name: fis-airflow` at the top. Without a
> project name, Docker would derive one from the directory, which is the same name the
> main stack uses. Both files define services called `postgres` and `redis`, so they would
> fight over the same container names. `fis-airflow` rather than plain `airflow` also
> keeps it clear of any unrelated Airflow you already run on this machine.

First run pulls ~2 GB of images, builds the Airflow image from `airflow/`, and runs
`airflow-init` (database migration + admin user), so allow 3–5 minutes. Watch progress with:

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

### The example DAGs

[`dags/hello_airflow.py`](../../dags/hello_airflow.py) is the smallest starting point: a bash
task, then extract → transform → load on hard-coded data, with no network access needed.

Four `parallel_*` DAGs show the ways tasks can run at the same time. They use made-up
data and `schedule=None`, so they run only when you trigger them. Each one's docs (shown
in the UI) say what to look for:

| DAG | Pattern |
|---|---|
| [`parallel_01_fan_out_fan_in`](../../dags/parallel_01_fan_out_fan_in.py) | Independent tasks run side by side, then one task waits for all of them |
| [`parallel_02_dynamic_mapping`](../../dags/parallel_02_dynamic_mapping.py) | `.expand()` makes one task per ticker at run time, reading the list from the `watchlist_tickers` Variable; `max_active_tis_per_dag` caps how many run at once |
| [`parallel_03_task_groups`](../../dags/parallel_03_task_groups.py) | One small pipeline per region, each in a TaskGroup, all regions in parallel |
| [`parallel_04_partial_failure`](../../dags/parallel_04_partial_failure.py) | `trigger_rule="all_done"` merges what the parallel tasks returned, even if one failed |

`parallel_02` and `market_daily_snapshot` (below) both read their tickers from the same
Variable, so one change updates both. To change it without editing code, set it in the UI under
**Admin → Variables** (key `watchlist_tickers`, value `AAPL,MSFT,NVDA`), or:

```bash
docker compose -f docker-compose-airflow.yaml exec airflow-scheduler airflow variables set watchlist_tickers AAPL,MSFT,NVDA
```

[`dags/market_daily_snapshot.py`](../../dags/market_daily_snapshot.py) fetches closing
prices for the tickers in the `watchlist_tickers` Variable (four defaults if it isn't set),
ranks them by daily return, and writes one JSON report per run
to `data/processed/market_snapshots/`. Unpause it in the UI, or:

```bash
make airflow-dag                                    # trigger one run
cat data/processed/market_snapshots/*.json          # read the output
```

It exists to show what a scheduler buys you over a `for` loop:

| Airflow feature | Where to look |
|---|---|
| Dynamic task mapping — one task per ticker, run in parallel | `fetch_one.expand(ticker=...)` |
| The number of parallel tasks follows a Variable, with no code change | `list_tickers` reads `watchlist_tickers` |
| Per-item retry boundary — one throttled symbol doesn't re-fetch the others | `retries` in `default_args` |
| Retryable vs. permanent failure | `RuntimeError` on `YFRateLimitError` vs. `AirflowFailException` on an empty frame |
| Idempotent output, so re-runs and backfills are safe | filename keyed by the run's date in `write_report` |
| XCom for small values only | the docstring on `summarize` |
| `catchup=False` to avoid a surprise backfill | the `@dag` decorator |

### Adding Python packages for your DAGs

Add the package to [`airflow/requirements.txt`](../../airflow/requirements.txt) (that's where
`yfinance` comes from) and run `make airflow-up`. It passes `--build`, so the image is rebuilt
(Docker reuses cached layers, so only the `pip install` step reruns) and the containers are
recreated. DAG edits need no rebuild; package changes do. System (apt) packages go in
[`airflow/Dockerfile`](../../airflow/Dockerfile), which has a commented template.

Don't use `_PIP_ADDITIONAL_REQUIREMENTS` for this. It re-runs `pip install` on *every*
container start, about 40 seconds × 6 containers. See
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
  `docker compose -f docker-compose-airflow.yaml logs airflow-init`.
- **`Bind for 0.0.0.0:8080 failed: port is already allocated`** → see §3.
- **Containers stuck `(health: starting)`** → normal for the first 60–90 s after
  `airflow-init` completes. Only worry after ~3 minutes.
- **`ModuleNotFoundError` for a package in a DAG** → add it to `airflow/requirements.txt` and
  run `make airflow-up` again (§4).
- **Empty DAG list but your file is in `dags/`** → check for an import error under
  *Browse → DAG Import Errors* in the UI, or run `make airflow-cli CMD="dags list-import-errors"`.

---

## 6. Where this is heading

Right now Airflow is standalone scaffolding. The intended use is scheduling the ingestion
workers in [`services/ingestion/*`](../../services/ingestion) — the nightly market-data,
filings and news pulls — so the backend serves from a warm store instead of hitting Yahoo
on the request path. See [`ARCHITECTURE.md`](../../ARCHITECTURE.md).
