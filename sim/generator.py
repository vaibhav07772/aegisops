"""Generates simulated telemetry for a tick."""
from __future__ import annotations

import random
from datetime import datetime

from sim.config import (
    SCENARIOS,
    SERVICE_MAP,
    SERVICE_NAMES,
    MetricOverride,
    ServiceProfile,
)
from sim.models import (
    IncidentScenario,
    LogEvent,
    MetricPoint,
    Span,
    new_id,
    utc_now,
)

METRIC_NAMES = ("cpu_percent", "memory_mb", "latency_p95_ms", "error_rate", "requests_per_sec")


class TelemetryGenerator:
    """Generates one tick of metrics/logs/traces for a scenario."""

    def __init__(self, scenario: IncidentScenario, seed: int | None = None):
        self.scenario = scenario
        self.definition = SCENARIOS[scenario.value]
        self.rng = random.Random(seed)
        self._overrides = self._index_overrides()
        self._error_templates = self.definition.error_log_templates

    def _index_overrides(self) -> dict[str, dict[str, MetricOverride]]:
        idx: dict[str, dict[str, MetricOverride]] = {}
        for ov in self.definition.metric_overrides:
            idx.setdefault(ov.service, {})[ov.metric] = ov
        return idx

    def _metric_value(self, service: ServiceProfile, metric: str, progress: float) -> float:
        base = getattr(service, f"base_{metric}")

        # Scenario-specific time-varying behaviors
        if (
            metric == "memory_mb"
            and self.scenario == IncidentScenario.MEMORY_LEAK
            and service.name == "order-service"
        ):
            return round(base + 1200.0 * progress + self.rng.gauss(0, 10), 4)

        if (
            metric == "cpu_percent"
            and self.scenario == IncidentScenario.CPU_SPIKE
            and service.name == "api-gateway"
        ):
            ramp = min(1.0, progress * 5)
            return round(base * (1 + 1.6 * ramp) + self.rng.gauss(0, 3), 4)

        if (
            metric == "error_rate"
            and self.scenario == IncidentScenario.ERROR_CASCADE
            and service.name == "auth-service"
        ):
            ramp = min(1.0, progress * 3)
            return round(min(1.0, max(0.0, base + 0.45 * ramp + self.rng.gauss(0, 0.02))), 4)

        if (
            metric == "error_rate"
            and self.scenario == IncidentScenario.SERVICE_OUTAGE
            and service.name == "payment-service"
        ):
            ramp = min(1.0, progress * 4)
            return round(min(1.0, base + 1.0 * ramp), 4)

        value = base
        ov = self._overrides.get(service.name, {}).get(metric)
        if ov is not None:
            value = value * ov.multiplier + ov.offset

        sigma = 0.05 * abs(value) if value > 0 else 0.0
        value += self.rng.gauss(0, sigma)

        if metric == "error_rate":
            value = max(0.0, min(1.0, value))
        elif metric == "cpu_percent":
            value = max(0.0, min(100.0, value))
        else:
            value = max(0.0, value)

        return round(value, 4)

    def tick(
        self,
        timestamp: datetime | None = None,
        progress: float = 0.0,
    ) -> tuple[list[MetricPoint], list[LogEvent], list[Span]]:
        ts = timestamp or utc_now()
        metrics: list[MetricPoint] = []
        logs: list[LogEvent] = []
        spans: list[Span] = []

        for svc_name in SERVICE_NAMES:
            sp = SERVICE_MAP[svc_name]
            values: dict[str, float] = {}
            for metric in METRIC_NAMES:
                val = self._metric_value(sp, metric, progress)
                values[metric] = val
                metrics.append(
                    MetricPoint(
                        timestamp=ts,
                        service=svc_name,
                        metric_name=metric,
                        value=val,
                    )
                )

            error_rate = values["error_rate"]
            rps = values["requests_per_sec"]

            # --- Error / warning logs ---
            error_count = int(rps * 0.1 * error_rate * self.rng.uniform(0.5, 1.5))
            for _ in range(error_count):
                lvl, tmpl = self._pick_error_template(svc_name)
                logs.append(
                    LogEvent(
                        timestamp=ts,
                        service=svc_name,
                        level=lvl,
                        message=tmpl.format(
                            ms=self.rng.randint(500, 5000),
                            pct=self.rng.randint(80, 99),
                            route=self.rng.choice(sp.operations),
                            user_id=self.rng.randint(1000, 9999),
                            order_id=new_id("ord_"),
                            n=self.rng.randint(10, 500),
                        ),
                    )
                )

            # --- Info logs ---
            if rps > 1:
                op = self.rng.choice(sp.operations)
                logs.append(
                    LogEvent(
                        timestamp=ts,
                        service=svc_name,
                        level="INFO",
                        message=f"Handled {op} in {int(values['latency_p95_ms'])}ms",
                    )
                )

            # --- Spans (sample 0-3 requests per service per tick) ---
            num_requests = max(0, min(3, int(rps / 50)))
            for _ in range(num_requests):
                trace_id = new_id()
                root_span_id = new_id()
                op = self.rng.choice(sp.operations)
                dur = max(
                    1.0,
                    self.rng.gauss(values["latency_p95_ms"], values["latency_p95_ms"] * 0.2),
                )
                status = "error" if self.rng.random() < error_rate else "ok"
                spans.append(
                    Span(
                        timestamp=ts,
                        trace_id=trace_id,
                        span_id=root_span_id,
                        parent_span_id=None,
                        service=svc_name,
                        operation=op,
                        duration_ms=round(dur, 2),
                        status=status,
                    )
                )
                for up in sp.upstream:
                    up_svc = SERVICE_MAP.get(up)
                    if not up_svc:
                        continue
                    up_dur = max(1.0, self.rng.gauss(values["latency_p95_ms"] * 0.6, 5))
                    spans.append(
                        Span(
                            timestamp=ts,
                            trace_id=trace_id,
                            span_id=new_id(),
                            parent_span_id=root_span_id,
                            service=up,
                            operation="internal_call",
                            duration_ms=round(up_dur, 2),
                            status="error" if self.rng.random() < error_rate else "ok",
                        )
                    )

        return metrics, logs, spans

    def _pick_error_template(self, service: str) -> tuple[str, str]:
        if service in self.definition.affected_services and self._error_templates:
            return self.rng.choice(self._error_templates)
        return self.rng.choice([
            ("ERROR", "Upstream call failed: timeout after {ms}ms"),
            ("WARN", "Slow request: {ms}ms"),
        ])