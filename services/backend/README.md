# Core Backend

**Release:** R1+  |  **Port:** 8000  |  **Kind:** fastapi

Orchestrates ingestion, analytics, RAG and agents; serves the frontend.

## Run locally

```bash
cd services/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
