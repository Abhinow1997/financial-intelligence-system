# Filings Ingestor (R2)
# Unstructured 10-K/10-Q/proxy PDF ingestion for RAG.
# Worker exposes /health for compose + POST /run to trigger a batch, and a
# run_once() you can call from a scheduler (cron / Kafka consumer loop).
from fastapi import FastAPI

app = FastAPI(title="Filings Ingestor", version="0.1.0")
SERVICE = "filings"
RELEASE = "R2"


def run_once() -> dict:
    # TODO: implement one ingestion/processing cycle.
    return {"service": SERVICE, "ingested": 0, "status": "not_implemented"}


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.post("/run")
def run():
    return run_once()


if __name__ == "__main__":
    print(run_once())
