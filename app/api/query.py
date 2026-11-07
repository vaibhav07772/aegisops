"""Telemetry query API endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.storage import repositories as repo
from app.storage.database import get_session

router = APIRouter(prefix="/api/v1", tags=["query"])


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricSeriesResponse(BaseModel):
    service: str
    metric_name: str
    run_id: str | None
    count: int
    points: list[MetricPoint]


class LogItem(BaseModel):
    timestamp: datetime
    service: str
    level: str
    message: str
    run_id: str
    trace_id: str | None = None


class SpanItem(BaseModel):
    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: str | None
    service: str
    operation: str
    duration_ms: float
    status: str


class RunSummary(BaseModel):
    run_id: str
    scenario: str
    ingested_at: datetime
    metrics_count: int
    logs_count: int
    spans_count: int


@router.get("/runs", response_model=list[RunSummary])
def list_runs(session: Session = Depends(get_session)):
    rows = repo.list_ingested_runs(session)
    return [
        RunSummary(
            run_id=r.run_id,
            scenario=r.scenario,
            ingested_at=r.ingested_at,
            metrics_count=r.metrics_count,
            logs_count=r.logs_count,
            spans_count=r.spans_count,
        )
        for r in rows
    ]


@router.get("/services", response_model=list[str])
def list_services(session: Session = Depends(get_session)):
    return repo.list_services(session)


@router.get("/metric-names", response_model=list[str])
def list_metric_names(session: Session = Depends(get_session)):
    return repo.list_metric_names(session)


@router.get("/metrics/series", response_model=MetricSeriesResponse)
def metric_series(
    service: str,
    metric: str = Query(..., description="cpu_percent|memory_mb|latency_p95_ms|error_rate|requests_per_sec"),
    run_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(1000, ge=1, le=10000),
    session: Session = Depends(get_session),
):
    rows = repo.query_metric_series(
        session,
        service=service,
        metric_name=metric,
        run_id=run_id,
        start=start,
        end=end,
        limit=limit,
    )
    if not rows:
        raise HTTPException(404, "no metric points matched the query")
    return MetricSeriesResponse(
        service=service,
        metric_name=metric,
        run_id=run_id,
        count=len(rows),
        points=[MetricPoint(timestamp=r.timestamp, value=r.value) for r in rows],
    )


@router.get("/logs", response_model=list[LogItem])
def list_logs(
    service: str | None = None,
    level: str | None = None,
    run_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    rows = repo.query_logs(
        session,
        service=service,
        level=level,
        run_id=run_id,
        start=start,
        end=end,
        limit=limit,
    )
    return [
        LogItem(
            timestamp=r.timestamp,
            service=r.service,
            level=r.level,
            message=r.message,
            run_id=r.run_id,
            trace_id=r.trace_id,
        )
        for r in rows
    ]


@router.get("/traces", response_model=list[SpanItem])
def list_recent_traces(
    service: str | None = None,
    status: str | None = Query(None, pattern="^(ok|error)$"),
    run_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    rows = repo.list_recent_traces(
        session, service=service, status=status, run_id=run_id, limit=limit
    )
    return [
        SpanItem(
            timestamp=r.timestamp,
            trace_id=r.trace_id,
            span_id=r.span_id,
            parent_span_id=r.parent_span_id,
            service=r.service,
            operation=r.operation,
            duration_ms=r.duration_ms,
            status=r.status,
        )
        for r in rows
    ]


@router.get("/traces/{trace_id}", response_model=list[SpanItem])
def get_trace(trace_id: str, session: Session = Depends(get_session)):
    rows = repo.get_trace_spans(session, trace_id)
    if not rows:
        raise HTTPException(404, f"trace '{trace_id}' not found")
    return [
        SpanItem(
            timestamp=r.timestamp,
            trace_id=r.trace_id,
            span_id=r.span_id,
            parent_span_id=r.parent_span_id,
            service=r.service,
            operation=r.operation,
            duration_ms=r.duration_ms,
            status=r.status,
        )
        for r in rows
    ]