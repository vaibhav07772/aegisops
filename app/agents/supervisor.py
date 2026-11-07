"""Supervisor — decides which agent to invoke next."""
from __future__ import annotations

from app.agents.state import IncidentState
from app.logging_config import get_logger

logger = get_logger("agents.supervisor")

MAX_STEPS = 16


def supervisor_node(state: IncidentState) -> dict:
    step = len(state.get("timeline", []))
    if step > MAX_STEPS:
        logger.warning("supervisor_max_steps_exceeded", step=step)
        return {
            "timeline": [
                {"agent": "supervisor", "action": "abort", "reason": "max_steps_exceeded"}
            ]
        }
    return {
        "timeline": [{"agent": "supervisor", "action": "route", "step": step}]
    }


def route_from_supervisor(state: IncidentState) -> str:
    """Decide next node based on state completion."""
    if len(state.get("timeline", [])) > MAX_STEPS:
        return "__end__"
    if not state.get("metric_findings"):
        return "metric_agent"
    if not state.get("log_findings"):
        return "log_agent"
    if not state.get("trace_findings"):
        return "trace_agent"
    if "runbook_context" not in state:
        return "runbook_agent"
    if not state.get("root_cause"):
        return "reasoner"
    if not state.get("remediation"):
        return "remediation_agent"
    return "__end__"