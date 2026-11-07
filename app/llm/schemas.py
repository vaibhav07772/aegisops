"""Pydantic schemas for LLM structured outputs.

Lenient: aliases, defaults, and normalizers so minor LLM variations don't fail.
"""
from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

_ALLOWED_CATEGORIES = {
    "memory", "errors", "latency", "cpu", "traffic", "healthy", "unknown"
}
_CATEGORY_ALIASES = {
    "mem": "memory",
    "memory_leak": "memory",
    "error": "errors",
    "error_rate": "errors",
    "slow": "latency",
    "database": "latency",
    "db": "latency",
    "slow_database": "latency",
    "cpu_spike": "cpu",
    "cpu_high": "cpu",
    "network": "traffic",
    "load": "traffic",
    "normal": "healthy",
    "ok": "healthy",
    "no_anomaly": "healthy",
}

_ALLOWED_ACTIONS = {
    "no_action", "restart_service", "rollback_deployment",
    "scale_horizontally", "inspect_traffic_source", "investigate_manually",
}
_ACTION_ALIASES = {
    "restart": "restart_service",
    "rolling_restart": "restart_service",
    "rollback": "rollback_deployment",
    "revert": "rollback_deployment",
    "scale": "scale_horizontally",
    "horizontal_scale": "scale_horizontally",
    "scale_out": "scale_horizontally",
    "add_replicas": "scale_horizontally",
    "inspect": "inspect_traffic_source",
    "investigate": "investigate_manually",
    "manual": "investigate_manually",
    "none": "no_action",
    "noop": "no_action",
    "ignore": "no_action",
}

_ALLOWED_RISKS = {"none", "low", "medium", "high"}


def _normalize_category(v) -> str:
    if v is None:
        return "unknown"
    s = str(v).lower().strip().replace(" ", "_").replace("-", "_")
    if s in _ALLOWED_CATEGORIES:
        return s
    return _CATEGORY_ALIASES.get(s, "unknown")


def _normalize_action(v) -> str:
    if not v:
        return "investigate_manually"
    s = str(v).lower().strip().replace(" ", "_").replace("-", "_")
    if s in _ALLOWED_ACTIONS:
        return s
    return _ACTION_ALIASES.get(s, "investigate_manually")


def _normalize_confidence(v) -> str:
    if not v:
        return "low"
    s = str(v).lower().strip()
    if s in {"low", "medium", "high"}:
        return s
    return "low"


def _normalize_risk(v, default: str = "medium") -> str:
    if not v:
        return default
    s = str(v).lower().strip()
    if s in _ALLOWED_RISKS:
        return s
    return default


def _normalize_int_severity(v, lo: int = 0, hi: int = 3) -> int:
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return lo


class LLMCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    service: str = ""
    metric: str = ""
    severity: int = Field(default=1, ge=0, le=3)
    baseline_ratio: float | None = None
    reason: str = Field(default="", max_length=500)

    @field_validator("severity", mode="before")
    @classmethod
    def _sev(cls, v):
        return _normalize_int_severity(v, 0, 3)


class LLMRootCause(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    category: Literal[
        "memory", "errors", "latency", "cpu", "traffic", "healthy", "unknown"
    ] = "unknown"
    primary_service: str | None = None
    primary_metric: str | None = None
    hypothesis: str = Field(default="", max_length=800)
    confidence: Literal["low", "medium", "high"] = "low"
    severity: int = Field(default=0, ge=0, le=3)
    evidence_summary: list[str] = Field(default_factory=list)
    candidates: list[LLMCandidate] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        return _normalize_category(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        return _normalize_confidence(v)

    @field_validator("severity", mode="before")
    @classmethod
    def _sev(cls, v):
        return _normalize_int_severity(v, 0, 3)

    @field_validator("evidence_summary", mode="before")
    @classmethod
    def _ev(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x][:10]
        return []

    @field_validator("candidates", mode="before")
    @classmethod
    def _cands(cls, v):
        if not isinstance(v, list):
            return []
        return v[:8]


class LLMRemediationStep(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    order: int = Field(default=1, ge=1)
    action: str = ""
    command: str | None = None
    reason: str = Field(default="", max_length=500)
    risk: Literal["low", "medium", "high"] = "medium"

    @field_validator("risk", mode="before")
    @classmethod
    def _risk(cls, v):
        r = _normalize_risk(v, default="medium")
        return r if r in {"low", "medium", "high"} else "medium"

    @field_validator("order", mode="before")
    @classmethod
    def _ord(cls, v):
        try:
            return max(1, int(float(v)))
        except (TypeError, ValueError):
            return 1


class LLMRemediation(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    action: Literal[
        "no_action", "restart_service", "rollback_deployment",
        "scale_horizontally", "inspect_traffic_source", "investigate_manually",
    ] = "investigate_manually"
    target_service: str | None = None
    reason: str = Field(default="", max_length=800)
    risk_level: Literal["none", "low", "medium", "high"] = "medium"
    requires_approval: bool = True
    steps: list[LLMRemediationStep] = Field(default_factory=list)
    estimated_mttr_minutes: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "estimated_mttr_minutes",
            "mttr_minutes",
            "mttr",
            "r_estimate_minutes",
            "estimate_minutes",
            "eta_minutes",
        ),
        ge=0,
        le=180,
    )

    @field_validator("action", mode="before")
    @classmethod
    def _act(cls, v):
        return _normalize_action(v)

    @field_validator("risk_level", mode="before")
    @classmethod
    def _rl(cls, v):
        return _normalize_risk(v, default="medium")

    @field_validator("requires_approval", mode="before")
    @classmethod
    def _ra(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in {"true", "yes", "1", "y"}
        if isinstance(v, (int, float)):
            return bool(v)
        return True

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, v):
        if not isinstance(v, list):
            return []
        return v[:8]

    @field_validator("estimated_mttr_minutes", mode="before")
    @classmethod
    def _mttr(cls, v):
        if v is None:
            return None
        try:
            n = int(float(v))
            return max(0, min(180, n))
        except (TypeError, ValueError):
            return None