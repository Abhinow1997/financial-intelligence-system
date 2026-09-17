# Model Gateway (Platform)
# Model abstraction, routing/cascade, prompt caching, provider failover.
from fastapi import FastAPI

app = FastAPI(title="Model Gateway", version="0.1.0")

SERVICE = "model_gateway"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Model abstraction, routing/cascade, prompt caching, provider failover.",
        "docs": "/docs",
    }
