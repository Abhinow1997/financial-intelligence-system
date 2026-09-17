# Filings Ingestor

**Release:** R2  |  **Port:** 8102  |  **Kind:** worker

Unstructured 10-K/10-Q/proxy PDF ingestion for RAG.

## Run locally

```bash
cd services/ingestion/filings
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8102
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
