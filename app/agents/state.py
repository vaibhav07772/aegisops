"""LangGraph state definition for incident analysis."""
from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict


class IncidentState(TypedDict, total=False):
    # Input
    incident_id: str
    run_id: str
    scenario: str

    # Agent outputs
    metric_findings: dict
    log_findings: dict
    trace_findings: dict
    runbook_context: list[dict]
    root_cause: dict
    remediation: dict

    # Audit trail (append-only)
    timeline: Annotated[list[dict], add]