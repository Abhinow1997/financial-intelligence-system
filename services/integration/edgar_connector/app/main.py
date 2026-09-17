# EDGAR Connector (R2)
# SEC EDGAR filing retrieval adapter.
from fastapi import FastAPI

app = FastAPI(title="EDGAR Connector", version="0.1.0")

SERVICE = "edgar_connector"
RELEASE = "R2"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "SEC EDGAR filing retrieval adapter.",
        "docs": "/docs",
    }
