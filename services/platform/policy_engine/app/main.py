# Policy Engine (Platform)
# Runtime policy, approval gates, human-in-the-loop, kill switch.
from fastapi import FastAPI

app = FastAPI(title="Policy Engine", version="0.1.0")

SERVICE = "policy_engine"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Runtime policy, approval gates, human-in-the-loop, kill switch.",
        "docs": "/docs",
    }
