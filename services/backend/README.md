# Core Backend

**Release:** R1+  |  **Port:** 8000  |  **Kind:** fastapi

Orchestrates ingestion, analytics, RAG and agents; serves the frontend.

## Run locally

Dependencies for this service come from the **root** `pyproject.toml` (Poetry),
not a per-service `requirements.txt`:

```bash
poetry install                      # from the repo root, once
cd services/backend
poetry run uvicorn app.main:app --reload --port 8000
```

Or in Docker — note the build context is the repo root:

```bash
docker build -f services/backend/Dockerfile -t fis-backend .
```

## Endpoints

- `GET /health` - liveness
- `GET /docs` - OpenAPI
- `POST /ask` - grounded answer (stub, R2)

### Market data (Lab 01, backed by yfinance)

- `GET /market/quote/{ticker}` - latest price snapshot
- `GET /market/history/{ticker}?period=&interval=` - OHLCV series
- `GET /market/fundamentals/{ticker}` - company profile + valuation
- `POST /market/compare` - rank 2-5 symbols by return over a period

Walkthrough: [`docs/labs/lab01_fastapi_yfinance.md`](../../docs/labs/lab01_fastapi_yfinance.md).

## Where this fits

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md) and the release notes in [../../docs/releases/](../../docs/releases/).
