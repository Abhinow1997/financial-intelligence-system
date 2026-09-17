# Feature Store (R1)
# Feature/context layer; point-in-time correct features.
from fastapi import FastAPI

app = FastAPI(title="Feature Store", version="0.1.0")

SERVICE = "feature_store"
RELEASE = "R1"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Feature/context layer; point-in-time correct features.",
        "docs": "/docs",
    }
