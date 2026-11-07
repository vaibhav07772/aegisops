"""Incident CRUD + approval workflow state machine."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.storage.models import IncidentRow

VALID_TRANSITIONS = {
    "pending": {"approved", "rejected"},
    "approved": {"executed"},
    "rejected": set(),
    "executed": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upsert_from_analysis(
    session: Session,
    *,
    incident_id: str,
    run_id: str,
    scenario: str,
    analysis: dict,
) -> IncidentRow:
    """Insert or update incident from an analysis payload (idempotent)."""
    existing = session.execute(
        select(IncidentRow).where(IncidentRow.incident_id == incident_id)
    ).scalar_one_or_none()

    root_cause = analysis.get("root_cause") or {}
    remediation = analysis.get("remediation") or {}
    guardrail = remediation.get("guardrail_check") or {}
    violations = guardrail.get("violations") or []

    if existing is None:
        row = IncidentRow(
            incident_id=incident_id,
            run_id=run_id,
            scenario=scenario,
            analysis_json=json.dumps(analysis),
            root_cause_category=root_cause.get("category", "unknown"),
            root_cause_service=root_cause.get("primary_service"),
            severity=float(root_cause.get("severity", 0.0)),
            guardrail_passed=bool(guardrail.get("passed", True)),
            guardrail_violations_json=json.dumps(violations),
            status="pending",
            created_at=_now(),
        )
        session.add(row)
        session.flush()
        return row

    # Update analysis but preserve approval state
    existing.analysis_json = json.dumps(analysis)
    existing.root_cause_category = root_cause.get("category", "unknown")
    existing.root_cause_service = root_cause.get("primary_service")
    existing.severity = float(root_cause.get("severity", 0.0))
    existing.guardrail_passed = bool(guardrail.get("passed", True))
    existing.guardrail_violations_json = json.dumps(violations)
    session.flush()
    return existing


def list_incidents(
    session: Session,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[IncidentRow]:
    stmt = select(IncidentRow).order_by(desc(IncidentRow.created_at)).limit(limit)
    if status:
        stmt = stmt.where(IncidentRow.status == status)
    return list(session.scalars(stmt).all())


def get_incident(session: Session, incident_id: str) -> IncidentRow | None:
    return session.execute(
        select(IncidentRow).where(IncidentRow.incident_id == incident_id)
    ).scalar_one_or_none()


def approve(
    session: Session, incident_id: str, *, approver_name: str
) -> IncidentRow:
    row = get_incident(session, incident_id)
    if row is None:
        raise ValueError(f"Incident '{incident_id}' not found")
    if "approved" not in VALID_TRANSITIONS.get(row.status, set()):
        raise ValueError(
            f"Cannot approve incident in status '{row.status}'"
        )
    row.status = "approved"
    row.approved_by = approver_name
    row.approved_at = _now()
    session.flush()
    return row


def reject(
    session: Session, incident_id: str, *, reason: str, approver_name: str = "system"
) -> IncidentRow:
    row = get_incident(session, incident_id)
    if row is None:
        raise ValueError(f"Incident '{incident_id}' not found")
    if "rejected" not in VALID_TRANSITIONS.get(row.status, set()):
        raise ValueError(f"Cannot reject incident in status '{row.status}'")
    row.status = "rejected"
    row.rejection_reason = reason
    row.approved_by = approver_name
    row.approved_at = _now()
    session.flush()
    return row


def execute(
    session: Session, incident_id: str, *, executed_by: str
) -> IncidentRow:
    row = get_incident(session, incident_id)
    if row is None:
        raise ValueError(f"Incident '{incident_id}' not found")
    if "executed" not in VALID_TRANSITIONS.get(row.status, set()):
        raise ValueError(
            f"Cannot execute incident in status '{row.status}' (must approve first)"
        )

    analysis = json.loads(row.analysis_json)
    remediation = analysis.get("remediation") or {}
    steps = remediation.get("steps") or []

    lines = ["# DRY-RUN EXECUTION (kubectl not invoked — simulation mode)", ""]
    for step in steps:
        cmd = step.get("command")
        lines.append(f"[step {step.get('order')}] {step.get('action')}")
        if cmd:
            lines.append(f"  $ {cmd}")
            lines.append(f"  → [simulated OK] {step.get('reason', '')}")
        else:
            lines.append(f"  → [skipped — no command] {step.get('reason', '')}")
        lines.append("")
    if not steps:
        lines.append("(no steps to execute)")

    row.status = "executed"
    row.executed_at = _now()
    row.executed_by = executed_by
    row.execution_output = "\n".join(lines)
    session.flush()
    return row