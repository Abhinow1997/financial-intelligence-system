# Guardrails

**Release:** R5  |  **Port:** 8701  |  **Kind:** fastapi

Prompt-injection defenses, allowlists, schema checks, output filters.

## Run locally

```bash
cd services/security/guardrails
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8701
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
