"""Guardrails orchestrator — one function, all checks."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.monitoring import metrics as prom
from app.security.commands import check_command
from app.security.injection import check_injection
from app.security.permissions import is_allowed, required_role_for
from app.security.pii import redact

DEFAULT_ROLE = "operator"


@dataclass
class GuardrailReport:
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    redactions_applied: int = 0


def validate_remediation(
    remediation: dict,
    role: str = DEFAULT_ROLE,
) -> GuardrailReport:
    """
    Full guardrail check on a remediation plan.
    - Role permission for target action
    - Dangerous commands in steps
    - PII in reason/steps
    """
    report = GuardrailReport(passed=True)

    action = remediation.get("action", "investigate_manually")
    target = remediation.get("target_service")

    # 1) Role permission
    if not is_allowed(action, role):
        required = required_role_for(action)
        report.violations.append(
            f"permission: action='{action}' requires role='{required}', got='{role}'"
        )
        prom.guardrail_blocks_total.labels(guardrail_type="permission").inc()

    # 2) Command safety (each step)
    for step in remediation.get("steps", []) or []:
        cmd = step.get("command")
        if not cmd:
            continue
        check = check_command(cmd, allowlist_enabled=True)
        if not check.is_safe:
            report.violations.append(
                f"dangerous_cmd: step {step.get('order')} '{cmd[:80]}' — {check.reason}"
            )
            prom.guardrail_blocks_total.labels(guardrail_type="dangerous_cmd").inc()

    # 3) PII scrub (reason + steps)
    reason = remediation.get("reason", "") or ""
    r = redact(reason)
    if r.total:
        remediation["reason"] = r.text
        report.redactions_applied += r.total
        prom.guardrail_blocks_total.labels(guardrail_type="pii").inc()

    for step in remediation.get("steps", []) or []:
        for key in ("reason", "command"):
            val = step.get(key)
            if isinstance(val, str) and val:
                rr = redact(val)
                if rr.total:
                    step[key] = rr.text
                    report.redactions_applied += rr.total
                    prom.guardrail_blocks_total.labels(guardrail_type="pii").inc()

    # 4) Prompt injection in LLM output (defensive)
    text_blob = " ".join([
        reason,
        *[str(s.get("reason", "")) for s in remediation.get("steps", []) or []],
    ])
    inj = check_injection(text_blob)
    if not inj.is_safe:
        report.violations.append(f"injection: {inj.reason}")
        prom.guardrail_blocks_total.labels(guardrail_type="injection").inc()

    # 5) Extra scrutiny if target missing but action != no_action
    if action != "no_action" and not target:
        report.warnings.append("action_requires_target_service")

    report.passed = len(report.violations) == 0
    return report


def check_user_input(text: str) -> GuardrailReport:
    """For future chat endpoints — detect injection in user-provided text."""
    report = GuardrailReport(passed=True)
    inj = check_injection(text)
    if not inj.is_safe:
        report.violations.append(f"injection: {inj.reason}")
        prom.guardrail_blocks_total.labels(guardrail_type="injection").inc()
    r = redact(text)
    if r.total:
        report.redactions_applied = r.total
        prom.guardrail_blocks_total.labels(guardrail_type="pii").inc()
    report.passed = len(report.violations) == 0
    return report