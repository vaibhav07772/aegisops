"""Pydantic models for simulated telemetry."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class IncidentScenario(str, Enum):
    NORMAL = "normal"
    SLOW_DATABASE = "slow_database"
    MEMORY_LEAK = "memory_leak"
    CPU_SPIKE = "cpu_spike"
    ERROR_CASCADE = "error_cascade"
    SERVICE_OUTAGE = "service_outage"


class MetricPoint(BaseModel):
    timestamp: datetime
    service: str
    metric_name: str  # cpu_percent | memory_mb | latency_p95_ms | error_rate | requests_per_sec
    value: float
    labels: dict[str, Any] = Field(default_factory=dict)


class LogEvent(BaseModel):
    timestamp: datetime
    service: str
    level: str  # INFO | WARN | ERROR | FATAL
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    labels: dict[str, Any] = Field(default_factory=dict)


class Span(BaseModel):
    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    service: str
    operation: str
    duration_ms: float
    status: str = "ok"  # ok | error
    labels: dict[str, Any] = Field(default_factory=dict)


class SimulationMetadata(BaseModel):
    run_id: str
    scenario: IncidentScenario
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    tick_interval_seconds: float
    metrics_count: int
    logs_count: int
    spans_count: int
    services: list[str]
    config: dict[str, Any] = Field(default_factory=dict)