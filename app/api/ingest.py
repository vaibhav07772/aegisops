"""Ingestion API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.pipeline.ingestor import TelemetryIngestor
from app.storage.database import get_session

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("/run/{run_id}")
def ingest_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    ingestor = TelemetryIngestor()
    if run_id not in ingestor.available_runs():
        raise HTTPException(404, f"run_id '{run_id}' not found on disk")
    result = ingestor.ingest_run(run_id, session)
    if result is None:
        return {"run_id": run_id, "status": "already_ingested"}
    return {"run_id": run_id, "status": "ingested", "counts": result}


@router.post("/all")
def ingest_all(session: Session = Depends(get_session)) -> dict:
    ingestor = TelemetryIngestor()
    results = ingestor.ingest_all(session)
    return {"ingested": results, "count": len(results)}