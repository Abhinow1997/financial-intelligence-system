# Red-Team Suite

**Release:** R5  |  **Port:** 8702  |  **Kind:** worker

Attack library (indirect injection, tool misuse) + residual-risk reporting.

## Run locally

```bash
cd services/security/redteam
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8702
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
