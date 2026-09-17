# Prompt Registry (Platform)
# Versioned prompts/configs/tool-defs; pins mutable artifacts.
from fastapi import FastAPI

app = FastAPI(title="Prompt Registry", version="0.1.0")

SERVICE = "prompt_registry"
RELEASE = "Platform"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Versioned prompts/configs/tool-defs; pins mutable artifacts.",
        "docs": "/docs",
    }
