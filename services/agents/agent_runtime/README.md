# Agent Runtime

**Release:** R3  |  **Port:** 8511  |  **Kind:** agent

Bounded agent loop: state, memory, stopping logic, autonomy+cost budget, full trace.

## Run locally

```bash
cd services/agents/agent_runtime
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8511
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
