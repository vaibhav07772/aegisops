"""TraceAgent — finds slow and errored spans."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select

from app.agents.state import IncidentState
from app.logging_config import get_logger
from app.storage.database import get_session_factory
from app.storage.models import SpanRow

logger = get_logger("agents.trace")


def trace_agent_node(state: IncidentState) -> dict:
    run_id = state["run_id"]
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        rows = session.execute(
            select(
                SpanRow.trace_id,
                SpanRow.service,
                SpanRow.operation,
                SpanRow.duration_ms,
                SpanRow.status,
            ).where(SpanRow.run_id == run_id)
        ).all()

    if not rows:
        return {
            "trace_findings": {"slow_spans": [], "error_spans": [], "by_service": {}},
            "timeline": [{"agent": "trace_agent", "action": "no_traces_found"}],
        }

    durations_by_service: dict[str, list[float]] = defaultdict(list)
    error_spans: list[dict] = []
    for trace_id, svc, op, dur, status in rows:
        durations_by_service[svc].append(float(dur))
        if status == "error":
            error_spans.append(
                {
                    "trace_id": trace_id,
                    "service": svc,
                    "operation": op,
                    "duration_ms": round(float(dur), 2),
                }
            )

    # Slow spans per service: avg duration
    by_service_stats: dict[str, dict] = {}
    for svc, durs in durations_by_service.items():
        by_service_stats[svc] = {
            "span_count": len(durs),
            "avg_ms": round(sum(durs) / len(durs), 2),
            "max_ms": round(max(durs), 2),
        }

    error_by_service = Counter(s["service"] for s in error_spans)

    logger.info(
        "trace_agent_complete",
        run_id=run_id,
        total_spans=len(rows),
        error_spans=len(error_spans),
    )
    return {
        "trace_findings": {
            "total_spans": len(rows),
            "error_spans": error_spans[:20],
            "error_by_service": dict(error_by_service),
            "by_service": by_service_stats,
        },
        "timeline": [
            {
                "agent": "trace_agent",
                "action": "analyzed_traces",
                "spans": len(rows),
                "errors": len(error_spans),
            }
        ],
    }