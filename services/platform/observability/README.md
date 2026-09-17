# Observability

**Release:** Platform  |  **Port:** 8804  |  **Kind:** fastapi

Traces, cost/latency telemetry, drift monitors.

## Run locally

```bash
cd services/platform/observability
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8804
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
