# Evaluation Service

**Release:** R4  |  **Port:** 8601  |  **Kind:** fastapi

Deterministic + model graders, trajectory eval, regression, acceptance gates.

## Run locally

```bash
cd services/evaluation/eval_service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8601
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
