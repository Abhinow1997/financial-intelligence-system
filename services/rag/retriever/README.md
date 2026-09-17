# RAG Retriever

**Release:** R2  |  **Port:** 8402  |  **Kind:** retriever

Dense/sparse/hybrid retrieval + rerank + citations.

## Run locally

```bash
cd services/rag/retriever
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8402
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
