"""Role-based permissions for remediation actions."""
from __future__ import annotations

ROLE_LEVELS = {"read_only": 0, "operator": 1, "admin": 2}

ACTION_REQUIRED_ROLE: dict[str, str] = {
    "no_action": "read_only",
    "inspect_traffic_source": "read_only",
    "investigate_manually": "read_only",
    "restart_service": "operator",
    "scale_horizontally": "operator",
    "rollback_deployment": "admin",
}


def is_allowed(action: str, role: str) -> bool:
    required = ACTION_REQUIRED_ROLE.get(action, "admin")
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(required, 2)


def required_role_for(action: str) -> str:
    return ACTION_REQUIRED_ROLE.get(action, "admin")