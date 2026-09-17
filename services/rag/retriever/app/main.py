# RAG Retriever (R2) - retrieve + rerank + cite.
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="RAG Retriever", version="0.1.0")
SERVICE, RELEASE = "retriever", "R2"


class Query(BaseModel):
    query: str
    k: int = 5
    filters: dict = {}


class Chunk(BaseModel):
    doc_id: str
    text: str
    score: float
    citation: str


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "release": RELEASE}


@app.post("/retrieve")
def retrieve(q: Query):
    # TODO: embed query -> vector search (qdrant) -> hybrid + rerank -> cite.
    # Evaluate retrieval SEPARATELY from generation (recall@k, MRR, faithfulness).
    return {"query": q.query, "k": q.k, "chunks": [], "note": "not_implemented"}
