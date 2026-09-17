# Observability (Platform)
# Traces, cost/latency telemetry, drift monitors.
from fastapi import FastAPI

app = FastAPI(title="Observability", version="0.1.0")

SERVICE = "observability"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Traces, cost/latency telemetry, drift monitors.",
        "docs": "/docs",
    }
