# Broker Connector

**Release:** R3  |  **Port:** 8201  |  **Kind:** fastapi

State-changing portfolio/order connector. APPROVAL-GATED and reversible where possible.

## Run locally

```bash
cd services/integration/broker_connector
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8201
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
