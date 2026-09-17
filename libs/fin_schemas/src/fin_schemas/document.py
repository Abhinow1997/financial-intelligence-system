from pydantic import BaseModel


class DocumentChunk(BaseModel):
    doc_id: str
    text: str
    page: int | None = None
    citation: str
    score: float | None = None
