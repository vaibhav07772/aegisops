"""CRUD helpers for telemetry storage."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.storage.models import IngestionRun, LogRow, MetricRow, SpanRow


# ---------- Ingestion tracking ----------

def is_run_ingested(session: Session, run_id: str) -> bool:
    stmt = select(IngestionRun.id).where(IngestionRun.run_id == run_id).limit(1)
    return session.execute(stmt).first() is not None


def record_ingestion(
    session: Session,
    *,
    run_id: str,
    scenario: str,
    ingested_at: datetime,
    metrics_count: int,
    logs_count: int,
    spans_count: int,
) -> IngestionRun:
    row = IngestionRun(
        run_id=run_id,
        scenario=scenario,
        ingested_at=ingested_at,
        metrics_count=metrics_count,
        logs_count=logs_count,
        spans_count=spans_count,
    )
    session.add(row)
    session.flush()
    return row


def list_ingested_runs(session: Session) -> list[IngestionRun]:
    stmt = select(IngestionRun).order_by(desc(IngestionRun.ingested_at))
    return list(session.scalars(stmt).all())


# ---------- Bulk inserts ----------

def bulk_insert_metrics(session: Session, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    session.bulk_insert_mappings(MetricRow, rows)
    return len(rows)


def bulk_insert_logs(session: Session, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    session.bulk_insert_mappings(LogRow, rows)
    return len(rows)


def bulk_insert_spans(session: Session, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    session.bulk_insert_mappings(SpanRow, rows)
    return len(rows)


# ---------- Queries ----------

def query_metric_series(
    session: Session,
    *,
    service: str,
    metric_name: str,
    run_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 1000,
) -> list[MetricRow]:
    conds = [MetricRow.service == service, MetricRow.metric_name == metric_name]
    if run_id is not None:
        conds.append(MetricRow.run_id == run_id)
    if start is not None:
        conds.append(MetricRow.timestamp >= start)
    if end is not None:
        conds.append(MetricRow.timestamp <= end)
    stmt = (
        select(MetricRow)
        .where(and_(*conds))
        .order_by(MetricRow.timestamp.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def query_logs(
    session: Session,
    *,
    service: str | None = None,
    level: str | None = None,
    run_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[LogRow]:
    conds = []
    if service is not None:
        conds.append(LogRow.service == service)
    if level is not None:
        conds.append(LogRow.level == level)
    if run_id is not None:
        conds.append(LogRow.run_id == run_id)
    if start is not None:
        conds.append(LogRow.timestamp >= start)
    if end is not None:
        conds.append(LogRow.timestamp <= end)
    stmt = select(LogRow).order_by(desc(LogRow.timestamp)).limit(limit)
    if conds:
        stmt = stmt.where(and_(*conds))
    return list(session.scalars(stmt).all())


def list_recent_traces(
    session: Session,
    *,
    service: str | None = None,
    status: str | None = None,
    run_id: str | None = None,
    limit: int = 50,
) -> list[SpanRow]:
    conds = [SpanRow.parent_span_id.is_(None)]
    if service is not None:
        conds.append(SpanRow.service == service)
    if status is not None:
        conds.append(SpanRow.status == status)
    if run_id is not None:
        conds.append(SpanRow.run_id == run_id)
    stmt = (
        select(SpanRow)
        .where(and_(*conds))
        .order_by(desc(SpanRow.timestamp))
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def get_trace_spans(session: Session, trace_id: str) -> list[SpanRow]:
    stmt = (
        select(SpanRow)
        .where(SpanRow.trace_id == trace_id)
        .order_by(SpanRow.timestamp.asc())
    )
    return list(session.scalars(stmt).all())


def count_rows(session: Session, model) -> int:
    stmt = select(func.count()).select_from(model)
    return int(session.execute(stmt).scalar_one())


def list_services(session: Session) -> list[str]:
    stmt = select(MetricRow.service).distinct().order_by(MetricRow.service)
    return [r for r in session.scalars(stmt).all()]


def list_metric_names(session: Session) -> list[str]:
    stmt = select(MetricRow.metric_name).distinct().order_by(MetricRow.metric_name)
    return [r for r in session.scalars(stmt).all()]