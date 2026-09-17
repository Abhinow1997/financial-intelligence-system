# Tool Registry

**Release:** R3  |  **Port:** 8510  |  **Kind:** tools

Typed, validated finance tools (PV/DCF/VaR/screen) with minimum privilege.

## Run locally

```bash
cd services/agents/tool_registry
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8510
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
