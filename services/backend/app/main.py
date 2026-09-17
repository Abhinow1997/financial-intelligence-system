# Core Backend (R1+)
# Orchestrates ingestion, analytics, RAG and agents; serves the frontend.
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Core Backend", version="0.1.0")

SERVICE = "backend"
RELEASE = "R1+"


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.get("/")
def root():
    return {
        "service": SERVICE,
        "description": "Orchestrates ingestion, analytics, RAG and agents; serves the frontend.",
        "docs": "/docs",
    }


class AskRequest(BaseModel):
    question: str
    ticker: str | None = None


@app.post("/ask")
def ask(req: AskRequest):
    # TODO: fan out to retriever + model + agent, assemble grounded answer.
    return {
        "answer": "not_implemented",
        "citations": [],
        "cost_usd": 0.0,
        "latency_ms": 0,
    }
