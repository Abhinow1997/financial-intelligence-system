# Market Data Connector

**Release:** R1  |  **Port:** 8202  |  **Kind:** fastapi

Read-only vendor pricing API adapter with caching.

## Run locally

```bash
cd services/integration/marketdata_connector
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8202
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
