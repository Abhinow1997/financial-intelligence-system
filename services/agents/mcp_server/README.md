# MCP Server

**Release:** R3  |  **Port:** 8512  |  **Kind:** fastapi

Exposes a finance capability over MCP with documented trust boundaries.

## Run locally

```bash
cd services/agents/mcp_server
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8512
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
