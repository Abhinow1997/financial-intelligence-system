# RAG Indexer

**Release:** R2  |  **Port:** 8401  |  **Kind:** worker

Parse, chunk, embed and index documents into the vector store.

## Run locally

```bash
cd services/rag/indexer
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8401
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
