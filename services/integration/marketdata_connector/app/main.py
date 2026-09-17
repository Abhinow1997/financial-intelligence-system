# Market Data Connector (R1)
# Read-only vendor pricing API adapter with caching.
from fastapi import FastAPI

app = FastAPI(title="Market Data Connector", version="0.1.0")

SERVICE = "marketdata_connector"
RELEASE = "R1"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Read-only vendor pricing API adapter with caching.",
        "docs": "/docs",
    }
