# API Gateway

**Release:** Platform  |  **Port:** 8080  |  **Kind:** fastapi

Auth, rate limits, routing, redaction, audit; single entry point for the system.

## Run locally

```bash
cd services/gateway
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
