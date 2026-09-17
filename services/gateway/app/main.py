# API Gateway (Platform)
# Single entry point: auth, rate limits, routing, redaction, audit.
from fastapi import FastAPI

app = FastAPI(title="API Gateway", version="0.1.0")

SERVICE = "gateway"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Single entry point: auth, rate limits, routing, redaction, audit.",
        "docs": "/docs",
    }


# --- Downstream service map (routing table) ---------------------------
ROUTES = {
    "backend": "http://backend:8000",
    "model": "http://model_service:8302",
    "retriever": "http://retriever:8402",
    "agent": "http://agent_runtime:8511",
}


@app.get("/routes")
def routes():
    # In real life the gateway also enforces authN/Z, quotas, redaction, audit.
    return ROUTES
