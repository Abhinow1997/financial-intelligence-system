# Feature Store

**Release:** R1  |  **Port:** 8301  |  **Kind:** fastapi

Feature/context layer; point-in-time correct features.

## Run locally

```bash
cd services/analytics/feature_store
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8301
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
