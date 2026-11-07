"""Ground truth labels for all 6 AegisOps scenarios."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioTruth:
    scenario: str
    expected_category: str
    expected_service: str | None
    expected_metric: str | None
    expected_runbook: str | None


# Keyed by scenario name (evaluation runs map to these)
GROUND_TRUTH: dict[str, ScenarioTruth] = {
    "normal": ScenarioTruth(
        scenario="normal",
        expected_category="healthy",
        expected_service=None,
        expected_metric=None,
        expected_runbook=None,
    ),
    "memory_leak": ScenarioTruth(
        scenario="memory_leak",
        expected_category="memory",
        expected_service="order-service",
        expected_metric="memory_mb",
        expected_runbook="memory_leak",
    ),
    "slow_database": ScenarioTruth(
        scenario="slow_database",
        expected_category="latency",
        expected_service="postgres-db",
        expected_metric="latency_p95_ms",
        expected_runbook="slow_database",
    ),
    "service_outage": ScenarioTruth(
        scenario="service_outage",
        expected_category="errors",
        expected_service="payment-service",
        expected_metric="error_rate",
        expected_runbook="service_outage",
    ),
    "cpu_spike": ScenarioTruth(
        scenario="cpu_spike",
        expected_category="cpu",
        expected_service="api-gateway",
        expected_metric="cpu_percent",
        expected_runbook="cpu_spike",
    ),
    "error_cascade": ScenarioTruth(
        scenario="error_cascade",
        expected_category="errors",
        expected_service="auth-service",
        expected_metric="error_rate",
        expected_runbook="error_cascade",
    ),
}