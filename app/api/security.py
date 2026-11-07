"""Security guardrails API."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.security.commands import check_command
from app.security.guardrails import validate_remediation
from app.security.injection import check_injection
from app.security.pii import redact

router = APIRouter(prefix="/api/v1/security", tags=["security"])


class RedactRequest(BaseModel):
    text: str = Field(..., max_length=10000)


class RedactResponse(BaseModel):
    redacted: str
    counts: dict[str, int]
    total: int


class CommandCheckRequest(BaseModel):
    command: str = Field(..., max_length=2000)
    allowlist_enabled: bool = True


class CheckResponse(BaseModel):
    is_safe: bool
    reason: str | None = None
    matched_pattern: str | None = None


class InjectRequest(BaseModel):
    text: str = Field(..., max_length=10000)


class RemediationCheckRequest(BaseModel):
    remediation: dict
    role: str = Field("operator", pattern="^(read_only|operator|admin)$")


class RemediationCheckResponse(BaseModel):
    passed: bool
    violations: list[str]
    warnings: list[str]
    redactions_applied: int


@router.post("/redact", response_model=RedactResponse)
def pii_redact(req: RedactRequest) -> RedactResponse:
    r = redact(req.text)
    return RedactResponse(redacted=r.text, counts=r.counts, total=r.total)


@router.post("/check-command", response_model=CheckResponse)
def cmd_check(req: CommandCheckRequest) -> CheckResponse:
    c = check_command(req.command, allowlist_enabled=req.allowlist_enabled)
    return CheckResponse(
        is_safe=c.is_safe, reason=c.reason, matched_pattern=c.matched_pattern
    )


@router.post("/check-injection", response_model=CheckResponse)
def inject_check(req: InjectRequest) -> CheckResponse:
    c = check_injection(req.text)
    return CheckResponse(
        is_safe=c.is_safe, reason=c.reason, matched_pattern=c.matched_pattern
    )


@router.post("/check-remediation", response_model=RemediationCheckResponse)
def remediation_check(req: RemediationCheckRequest) -> RemediationCheckResponse:
    report = validate_remediation(req.remediation, role=req.role)
    return RemediationCheckResponse(
        passed=report.passed,
        violations=report.violations,
        warnings=report.warnings,
        redactions_applied=report.redactions_applied,
    )


@router.get("/health")
def security_health() -> dict:
    return {
        "status": "ready",
        "layers": [
            "pii_redaction",
            "command_blocklist",
            "command_allowlist",
            "role_permissions",
            "prompt_injection",
        ],
        "roles": ["read_only", "operator", "admin"],
    }