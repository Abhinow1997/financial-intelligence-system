# Prompt Registry

**Release:** Platform  |  **Port:** 8802  |  **Kind:** fastapi

Versioned prompts/configs/tool-defs; pins mutable artifacts.

## Run locally

```bash
cd services/platform/prompt_registry
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8802
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
