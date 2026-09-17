# Alt-Data Ingestor

**Release:** R1  |  **Port:** 8104  |  **Kind:** worker

Alternative data ingestion (sentiment, web, filings exhaust).

## Run locally

```bash
cd services/ingestion/altdata
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8104
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
