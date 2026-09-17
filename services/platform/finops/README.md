# FinOps / Unit Economics

**Release:** Platform  |  **Port:** 8805  |  **Kind:** fastapi

Cost metering, cost-per-completed-task, unit-economics rollups.

## Run locally

```bash
cd services/platform/finops
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8805
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
