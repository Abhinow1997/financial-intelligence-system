# Market Data Ingestor

**Release:** R1  |  **Port:** 8101  |  **Kind:** worker

Structured price/volume ingestion into the lake + feature store.

## Run locally

```bash
cd services/ingestion/market_data
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8101
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
