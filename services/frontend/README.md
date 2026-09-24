# Analyst Dashboard

**Release:** R1+  |  **Port:** 8501  |  **Kind:** streamlit

Streamlit analyst UI: predictions, RAG answers, agent traces, cost/latency.

## Run locally

Dependencies for this service come from the **root** `pyproject.toml` (Poetry),
not a per-service `requirements.txt`:

```bash
poetry install                      # from the repo root, once
cd services/frontend
poetry run streamlit run app/app.py
```

Or in Docker — note the build context is the repo root:

```bash
docker build -f services/frontend/Dockerfile -t fis-frontend .
```

## Endpoints

- Streamlit UI on `:8501`

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
