# Guardrails (R5)
# Prompt-injection defenses, allowlists, schema checks, output filters.
from fastapi import FastAPI

app = FastAPI(title="Guardrails", version="0.1.0")

SERVICE = "guardrails"
RELEASE = "R5"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Prompt-injection defenses, allowlists, schema checks, output filters.",
        "docs": "/docs",
    }
