"""Dangerous command blocklist + safe allowlist."""
from __future__ import annotations

import re
from dataclasses import dataclass

# (regex, label) — any match means BLOCK
BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-[rRfF]{1,3}\s+/", "recursive_rm_root"),
    (r"\brm\s+-rf\b", "recursive_rm"),
    (r"\bDROP\s+TABLE\b", "drop_table"),
    (r"\bTRUNCATE\s+TABLE\b", "truncate_table"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "delete_without_where"),
    (r"\bkubectl\s+delete\s+(?:namespace|ns)\b", "delete_namespace"),
    (r"\bkubectl\s+delete\s+\w+\s+--all\b", "delete_all_resources"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork_bomb"),
    (r"\bchmod\s+(?:777|a\+rwx)\b", "world_writable"),
    (r"\bdd\s+if=", "disk_dump"),
    (r"\bmkfs\.", "format_filesystem"),
    (r">\s*/dev/sd[a-z]", "disk_write"),
    (r"\s--privileged\b", "privileged_container"),
    (r"\s--force\b.*\s--all\b", "force_delete_all"),
    (r"\bgit\s+push\s+--force\b", "force_push"),
    (r"\bsudo\s+rm\b", "sudo_rm"),
    (r"\bcurl\b.*\|\s*(?:ba)?sh\b", "curl_pipe_shell"),
    (r"\bwget\b.*\|\s*(?:ba)?sh\b", "wget_pipe_shell"),
]

# Only these command prefixes are allowed (when enabled)
SAFE_PREFIXES: list[str] = [
    "kubectl get ",
    "kubectl describe ",
    "kubectl logs ",
    "kubectl top ",
    "kubectl rollout restart ",
    "kubectl rollout undo ",
    "kubectl rollout status ",
    "kubectl rollout history ",
    "kubectl scale ",
    "kubectl set resources ",
    "kubectl set env ",
    "kubectl exec ",
    "echo ",
    "printenv",
    "date",
]


@dataclass
class CommandCheck:
    is_safe: bool
    reason: str | None
    matched_pattern: str | None


def check_command(cmd: str, allowlist_enabled: bool = True) -> CommandCheck:
    if not cmd or not cmd.strip():
        return CommandCheck(is_safe=True, reason=None, matched_pattern=None)

    cmd_l = cmd.strip()

    # Blocklist first (hard fail)
    for pattern, label in BLOCK_PATTERNS:
        if re.search(pattern, cmd_l):
            return CommandCheck(
                is_safe=False,
                reason=f"blocked_pattern:{label}",
                matched_pattern=label,
            )

    # Allowlist (soft fail — command not in known-safe set)
    if allowlist_enabled:
        if not any(cmd_l.startswith(p) for p in SAFE_PREFIXES):
            return CommandCheck(
                is_safe=False,
                reason="not_in_allowlist",
                matched_pattern=None,
            )

    return CommandCheck(is_safe=True, reason=None, matched_pattern=None)