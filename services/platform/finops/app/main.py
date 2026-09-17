# FinOps / Unit Economics (Platform)
# Cost metering, cost-per-completed-task, unit-economics rollups.
from fastapi import FastAPI

app = FastAPI(title="FinOps / Unit Economics", version="0.1.0")

SERVICE = "finops"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Cost metering, cost-per-completed-task, unit-economics rollups.",
        "docs": "/docs",
    }
