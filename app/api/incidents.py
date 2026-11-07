"""Incident approval / rejection / execution API."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.storage import incidents as repo
from app.storage.database import get_session

logger = get_logger("api.incidents")
router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


class IncidentSummary(BaseModel):
    incident_id: str
    run_id: str
    scenario: str
    status: str
    category: str
    service: str | None
    severity: float
    guardrail_passed: bool
    created_at: datetime
    approved_by: str | None = None
    executed_at: datetime | None = None


class IncidentDetail(IncidentSummary):
    analysis: dict
    guardrail_violations: list[str] = []
    rejection_reason: str | None = None
    approved_at: datetime | None = None
    executed_by: str | None = None
    execution_output: str | None = None


class ApproveRequest(BaseModel):
    approver_name: str = Field(..., min_length=1, max_length=64)
    role: str = Field("operator", pattern="^(read_only|operator|admin)$")


class RejectRequest(BaseModel):
    approver_name: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=1, max_length=500)


class ExecuteRequest(BaseModel):
    executed_by: str = Field(..., min_length=1, max_length=64)


def _summary(row) -> IncidentSummary:
    return IncidentSummary(
        incident_id=row.incident_id,
        run_id=row.run_id,
        scenario=row.scenario,
        status=row.status,
        category=row.root_cause_category,
        service=row.root_cause_service,
        severity=row.severity,
        guardrail_passed=row.guardrail_passed,
        created_at=row.created_at,
        approved_by=row.approved_by,
        executed_at=row.executed_at,
    )


def _detail(row) -> IncidentDetail:
    return IncidentDetail(
        incident_id=row.incident_id,
        run_id=row.run_id,
        scenario=row.scenario,
        status=row.status,
        category=row.root_cause_category,
        service=row.root_cause_service,
        severity=row.severity,
        guardrail_passed=row.guardrail_passed,
        created_at=row.created_at,
        approved_by=row.approved_by,
        executed_at=row.executed_at,
        analysis=json.loads(row.analysis_json),
        guardrail_violations=json.loads(row.guardrail_violations_json or "[]"),
        rejection_reason=row.rejection_reason,
        approved_at=row.approved_at,
        executed_by=row.executed_by,
        execution_output=row.execution_output,
    )


@router.get("", response_model=list[IncidentSummary])
def list_incidents(
    status: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    rows = repo.list_incidents(session, status=status, limit=limit)
    return [_summary(r) for r in rows]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: str, session: Session = Depends(get_session)):
    row = repo.get_incident(session, incident_id)
    if row is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return _detail(row)


@router.post("/{incident_id}/approve", response_model=IncidentDetail)
def approve_incident(
    incident_id: str,
    req: ApproveRequest,
    session: Session = Depends(get_session),
):
    # Role gate — must be operator or admin
    if req.role == "read_only":
        raise HTTPException(403, "read_only role cannot approve")
    try:
        row = repo.approve(session, incident_id, approver_name=req.approver_name)
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(400, str(e)) from e
    logger.info("incident_approved", incident_id=incident_id, by=req.approver_name)
    return _detail(row)


@router.post("/{incident_id}/reject", response_model=IncidentDetail)
def reject_incident(
    incident_id: str,
    req: RejectRequest,
    session: Session = Depends(get_session),
):
    try:
        row = repo.reject(
            session,
            incident_id,
            reason=req.reason,
            approver_name=req.approver_name,
        )
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(400, str(e)) from e
    logger.info("incident_rejected", incident_id=incident_id, by=req.approver_name)
    return _detail(row)


@router.post("/{incident_id}/execute", response_model=IncidentDetail)
def execute_incident(
    incident_id: str,
    req: ExecuteRequest,
    session: Session = Depends(get_session),
):
    try:
        row = repo.execute(session, incident_id, executed_by=req.executed_by)
        session.commit()
    except ValueError as e:
        session.rollback()
        raise HTTPException(400, str(e)) from e
    logger.info("incident_executed", incident_id=incident_id, by=req.executed_by)
    return _detail(row)