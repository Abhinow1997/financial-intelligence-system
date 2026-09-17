# Model Service

**Release:** R1  |  **Port:** 8302  |  **Kind:** model

Predictive baseline+challenger (credit default). Model card. Deterministic agent tool.

## Run locally

```bash
cd services/analytics/model_service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8302
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
