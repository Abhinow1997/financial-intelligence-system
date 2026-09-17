# Broker Connector (R3)
# State-changing portfolio/order connector. APPROVAL-GATED and reversible where possible.
from fastapi import FastAPI

app = FastAPI(title="Broker Connector", version="0.1.0")

SERVICE = "broker_connector"
RELEASE = "R3"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": (
            "State-changing portfolio/order connector. "
            "APPROVAL-GATED and reversible where possible."
        ),
        "docs": "/docs",
    }
