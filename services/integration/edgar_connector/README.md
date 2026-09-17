# EDGAR Connector

**Release:** R2  |  **Port:** 8203  |  **Kind:** fastapi

SEC EDGAR filing retrieval adapter.

## Run locally

```bash
cd services/integration/edgar_connector
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8203
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
