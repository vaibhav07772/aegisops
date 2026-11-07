"""RAG search API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag.retriever import get_retriever

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(3, ge=1, le=10)


class SearchHit(BaseModel):
    runbook_id: str
    title: str
    section: str
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class IngestResponse(BaseModel):
    ingested: int
    message: str


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    r = get_retriever()
    if not r.is_ingested():
        raise HTTPException(
            503, "No runbooks ingested. Run: python scripts/ingest_runbooks.py"
        )
    hits = r.search(req.query, top_k=req.top_k)
    return SearchResponse(
        query=req.query,
        hits=[SearchHit(**h.__dict__) for h in hits],
    )


@router.post("/ingest", response_model=IngestResponse)
def ingest(force: bool = False) -> IngestResponse:
    r = get_retriever()
    result = r.ingest(force=force)
    return IngestResponse(**result)


@router.get("/health")
def health() -> dict:
    r = get_retriever()
    try:
        count = r.collection.count() if r.is_ingested() else 0
    except Exception:
        count = 0
    return {"status": "ready" if count > 0 else "empty", "runbook_chunks": count}