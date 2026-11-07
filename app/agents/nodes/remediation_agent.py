"""RemediationAgent — proposes a fix based on root cause."""
from __future__ import annotations

from app.agents.state import IncidentState
from app.logging_config import get_logger

logger = get_logger("agents.remediation")


_CATEGORY_ACTIONS: dict[str, dict] = {
    "healthy": {
        "action": "no_action",
        "reason": "No anomaly detected — continue monitoring",
        "risk": "none",
        "requires_approval": False,
    },
    "memory": {
        "action": "restart_service",
        "reason": "Memory pressure: rolling restart releases leaked memory",
        "risk": "medium",
        "requires_approval": True,
    },
    "errors": {
        "action": "rollback_deployment",
        "reason": "Elevated error rate: revert last deployment to last known good",
        "risk": "high",
        "requires_approval": True,
    },
    "latency": {
        "action": "scale_horizontally",
        "reason": "High latency: add replicas to spread load",
        "risk": "low",
        "requires_approval": True,
    },
    "cpu": {
        "action": "scale_horizontally",
        "reason": "CPU saturation: increase replica count",
        "risk": "low",
        "requires_approval": True,
    },
    "traffic": {
        "action": "inspect_traffic_source",
        "reason": "Unexpected traffic change: investigate source before scaling",
        "risk": "low",
        "requires_approval": True,
    },
    "unknown": {
        "action": "investigate_manually",
        "reason": "Insufficient signal for automated remediation",
        "risk": "medium",
        "requires_approval": True,
    },
}


def remediation_agent_node(state: IncidentState) -> dict:
    root_cause = state.get("root_cause", {})
    category = root_cause.get("category", "unknown")
    target = root_cause.get("primary_service")

    template = _CATEGORY_ACTIONS.get(category, _CATEGORY_ACTIONS["unknown"])

    if template["action"] == "no_action" or not target:
        dry_run = "# no action required"
    elif template["action"] == "restart_service":
        dry_run = f"kubectl rollout restart deployment/{target} -n production"
    elif template["action"] == "rollback_deployment":
        dry_run = f"kubectl rollout undo deployment/{target} -n production"
    elif template["action"] == "scale_horizontally":
        dry_run = f"kubectl scale deployment/{target} --replicas=+2 -n production"
    else:
        dry_run = f"# would {template['action']} on {target}"

    remediation = {
        "action": template["action"],
        "target_service": target,
        "reason": template["reason"],
        "risk_level": template["risk"],
        "requires_approval": template["requires_approval"],
        "executed": False,
        "dry_run_command": dry_run,
    }

    logger.info(
        "remediation_complete",
        action=remediation["action"],
        target=target,
        risk=remediation["risk_level"],
    )
    return {
        "remediation": remediation,
        "timeline": [
            {
                "agent": "remediation_agent",
                "action": f"proposed_{remediation['action']}",
                "target": target,
                "risk": remediation["risk_level"],
            }
        ],
    }