"""LogAgent — groups logs by service + level and surfaces error patterns."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import select

from app.agents.state import IncidentState
from app.logging_config import get_logger
from app.storage.database import get_session_factory
from app.storage.models import LogRow

logger = get_logger("agents.log")

# Normalize numeric IDs / durations so similar messages group together
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _normalize(msg: str) -> str:
    return _NUM_RE.sub("<N>", msg)[:200]


def log_agent_node(state: IncidentState) -> dict:
    run_id = state["run_id"]
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        rows = session.execute(
            select(LogRow.service, LogRow.level, LogRow.message).where(
                LogRow.run_id == run_id
            )
        ).all()

    if not rows:
        return {
            "log_findings": {"by_level": {}, "by_service": {}, "top_patterns": []},
            "timeline": [{"agent": "log_agent", "action": "no_logs_found"}],
        }

    by_level: Counter[str] = Counter()
    by_service: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    error_patterns: Counter[str] = Counter()

    for svc, level, message in rows:
        by_level[level] += 1
        by_service[svc] += 1
        normalized = _normalize(message)
        patterns[normalized] += 1
        if level in ("ERROR", "FATAL", "WARN"):
            error_patterns[normalized] += 1

    top_patterns = [
        {"pattern": p, "count": c} for p, c in error_patterns.most_common(10)
    ]

    logger.info(
        "log_agent_complete",
        run_id=run_id,
        total_logs=len(rows),
        error_logs=sum(c for lvl, c in by_level.items() if lvl in ("ERROR", "FATAL", "WARN")),
    )
    return {
        "log_findings": {
            "total_logs": len(rows),
            "by_level": dict(by_level),
            "by_service": dict(by_service),
            "top_patterns": top_patterns,
        },
        "timeline": [
            {
                "agent": "log_agent",
                "action": "analyzed_logs",
                "total": len(rows),
                "patterns": len(top_patterns),
            }
        ],
    }