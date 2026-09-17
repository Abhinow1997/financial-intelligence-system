# Evaluation Service (R4)
# Deterministic + model graders, trajectory eval, regression, acceptance gates.
from fastapi import FastAPI

app = FastAPI(title="Evaluation Service", version="0.1.0")

SERVICE = "eval_service"
RELEASE = "R4"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": (
            "Deterministic + model graders, trajectory eval, regression, acceptance gates."
        ),
        "docs": "/docs",
    }
