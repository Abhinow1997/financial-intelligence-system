# Financial Intelligence System (FIS)

> Base repository for **Big Data and Intelligent Analytics** (Northeastern, Fall 2026).
> One evolving financial AI system, built across six cumulative releases.

This monorepo is the skeleton your team grows across the semester:

```
DATA -> MODEL -> CONTEXT -> GENERATE -> RETRIEVE -> ACT -> EVALUATE -> ATTACK -> CONTROL -> RELEASE -> OPERATE -> SCALE -> MONETIZE
```

Every folder maps to a piece of that lifecycle. You do **not** build six unrelated
assignments - you extend *this* system, release by release, while measuring
**quality, cost, latency, and autonomy**.

---

## Quick start

```bash
# 1. Clone and enter
git clone <your-fork-url> financial-intelligence-system
cd financial-intelligence-system

# 2. Dev tooling + shared libraries
make setup            # or: pip install -r requirements-dev.txt

# 3. Run the tests (should be green on a fresh clone)
make test

# 4. Bring up the core stack (needs Docker)
make up-core          # gateway :8080  backend :8000  frontend :8501
```

Open the analyst dashboard at **http://localhost:8501**.

Other stack shapes: `make up-app` (backend + frontend only), `make up` (everything),
`make up-data` (datastores only), `make airflow-up` (Airflow UI on :8088 — see the
[Airflow runbook](docs/runbooks/airflow_local.md)).
No Docker? Run any single service directly - see its `README.md` (e.g.
[`services/analytics/model_service`](services/analytics/model_service/README.md)).

> **New to this repo? Start with the labs:**
> [`lab00 - git workflow`](docs/labs/lab00_git_workflow.md), then
> [`lab01 - FastAPI + yfinance`](docs/labs/lab01_fastapi_yfinance.md).
> Later: [`lab07 - GitHub Agentic Workflows`](docs/labs/lab07_github_agentic_workflows.md)
> (AI agents in CI, with [`gh-aw-lab/`](gh-aw-lab/README.md)).

---

## Repository map

| Path | Purpose | Release |
|---|---|---|
| [`services/frontend`](services/frontend) | Streamlit analyst dashboard | R1+ |
| [`services/gateway`](services/gateway) | API gateway: auth, routing, redaction, audit | Platform |
| [`services/backend`](services/backend) | Core orchestration API | R1+ |
| [`services/ingestion/*`](services/ingestion) | Market data, filings, news, alt-data ingestors | R1/R2 |
| [`services/integration/*`](services/integration) | Broker, market-data, EDGAR connectors | R1-R3 |
| [`services/analytics/*`](services/analytics) | Feature store + predictive model service | R1 |
| [`services/rag/*`](services/rag) | Indexer + retriever (grounding) | R2 |
| [`services/agents/*`](services/agents) | Tool registry, bounded agent runtime, MCP server | R3 |
| [`services/evaluation/*`](services/evaluation) | Evaluation harness/service | R4 |
| [`services/security/*`](services/security) | Guardrails + red-team suite | R5 |
| [`services/platform/*`](services/platform) | Model gateway, prompt registry, policy engine, observability, FinOps | R6/Platform |
| [`libs/*`](libs) | Shared Python packages (config, schemas, telemetry) | all |
| [`docs/`](docs) | Labs, architecture, release notes, engineering log, economics | all |
| [`evals/`](evals) | Golden + adversarial evaluation sets (versioned) | R4/R5 |
| [`data/`](data) | Local data lake (gitignored) + tiny committed samples | R1 |
| [`notebooks/`](notebooks) | Async pre-work (predictive + embeddings) | R1 |

Full picture: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## The six releases

| Release | Theme | You add | Evidence |
|---|---|---|---|
| **R1** | Data + Predict | ingestion, features, baseline+challenger model, model card | first unit-economics table |
| **R2** | Generate + Ground | document ingestion, RAG, structured output, citations | cost & latency per task |
| **R3** | Tool + Agentify | typed tools, bounded agent, autonomy budget, approvals | cost per completed task |
| **R4** | Evaluate + Validate | eval harness, graders, trajectory metrics | quality-per-dollar frontier |
| **R5** | Attack + Harden | threat model, prompt-injection attacks, mitigations | cost of controls |
| **R6** | Control + Deploy | versioned release, eval gate, canary, rollback | SLOs + TCO |

Each release has a checklist in [`docs/releases/`](docs/releases).

---

## How we work (git)

- `main` is always releasable. **No direct pushes.**
- Do work on a short-lived branch: `feat/r1-credit-model`, `fix/retriever-timeout`.
- Open a **Pull Request**, fill the template (incl. the AI Engineering Log), get a review, merge.
- Tag each release: `git tag -a v1.0-R1 -m "R1: Data + Predict"`.

The full workflow, with a hands-on exercise, is the first lab:
[`docs/labs/lab00_git_workflow.md`](docs/labs/lab00_git_workflow.md).
Conventions live in [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Ground rules

- **Never commit** secrets, API keys, or real financial/PII data. See [`.gitignore`](.gitignore) and [`SECURITY.md`](SECURITY.md).
- **State-changing** tools/integrations (e.g. placing an order) must pass the approval gate.
- Every major submission ships an **AI Engineering Log** (in the PR and [`docs/engineering-log/`](docs/engineering-log)).

## Tech

Python 3.12, FastAPI (services), Streamlit (frontend), Docker Compose (orchestration),
Postgres / Redis / Qdrant / MinIO / Redpanda (data backbone). Framework-agnostic by design.
