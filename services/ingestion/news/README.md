# News/Event Ingestor

**Release:** R1  |  **Port:** 8103  |  **Kind:** worker

Event/news stream ingestion (Kafka/Redpanda).

## Run locally

```bash
cd services/ingestion/news
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8103
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
