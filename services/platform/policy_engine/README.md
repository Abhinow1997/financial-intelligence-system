# Policy Engine

**Release:** Platform  |  **Port:** 8803  |  **Kind:** fastapi

Runtime policy, approval gates, human-in-the-loop, kill switch.

## Run locally

```bash
cd services/platform/policy_engine
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8803
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
