# Model Gateway

**Release:** Platform  |  **Port:** 8801  |  **Kind:** fastapi

Model abstraction, routing/cascade, prompt caching, provider failover.

## Run locally

```bash
cd services/platform/model_gateway
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8801
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
