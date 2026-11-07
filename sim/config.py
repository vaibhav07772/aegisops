"""Service definitions and scenario rules for the simulator."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceProfile:
    name: str
    base_cpu_percent: float
    base_memory_mb: float
    base_latency_p95_ms: float
    base_error_rate: float  # 0.0 - 1.0
    base_requests_per_sec: float
    upstream: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)


SERVICES: list[ServiceProfile] = [
    ServiceProfile(
        name="frontend",
        base_cpu_percent=25.0,
        base_memory_mb=180.0,
        base_latency_p95_ms=45.0,
        base_error_rate=0.005,
        base_requests_per_sec=120.0,
        upstream=["api-gateway"],
        operations=["GET /", "GET /products", "GET /cart"],
    ),
    ServiceProfile(
        name="api-gateway",
        base_cpu_percent=40.0,
        base_memory_mb=250.0,
        base_latency_p95_ms=30.0,
        base_error_rate=0.003,
        base_requests_per_sec=300.0,
        upstream=["auth-service", "order-service"],
        operations=["route_request", "rate_limit", "auth_check"],
    ),
    ServiceProfile(
        name="auth-service",
        base_cpu_percent=20.0,
        base_memory_mb=150.0,
        base_latency_p95_ms=25.0,
        base_error_rate=0.001,
        base_requests_per_sec=80.0,
        upstream=["postgres-db"],
        operations=["login", "verify_token", "refresh_token"],
    ),
    ServiceProfile(
        name="order-service",
        base_cpu_percent=35.0,
        base_memory_mb=320.0,
        base_latency_p95_ms=60.0,
        base_error_rate=0.002,
        base_requests_per_sec=50.0,
        upstream=["postgres-db", "payment-service"],
        operations=["create_order", "list_orders", "cancel_order"],
    ),
    ServiceProfile(
        name="payment-service",
        base_cpu_percent=30.0,
        base_memory_mb=200.0,
        base_latency_p95_ms=120.0,
        base_error_rate=0.01,
        base_requests_per_sec=25.0,
        upstream=[],
        operations=["charge_card", "refund", "verify_payment"],
    ),
    ServiceProfile(
        name="postgres-db",
        base_cpu_percent=50.0,
        base_memory_mb=1024.0,
        base_latency_p95_ms=15.0,
        base_error_rate=0.001,
        base_requests_per_sec=200.0,
        upstream=[],
        operations=["SELECT", "INSERT", "UPDATE"],
    ),
]

SERVICE_MAP = {s.name: s for s in SERVICES}
SERVICE_NAMES = [s.name for s in SERVICES]


@dataclass(frozen=True)
class MetricOverride:
    """Multiplier + additive offset for a specific service's metric."""
    service: str
    metric: str
    multiplier: float = 1.0
    offset: float = 0.0


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    label: str
    description: str
    metric_overrides: list[MetricOverride] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    duration_hint_seconds: int = 300
    error_log_templates: list[tuple[str, str]] = field(default_factory=list)


SCENARIOS: dict[str, ScenarioDefinition] = {
    "normal": ScenarioDefinition(
        name="normal",
        label="Normal operations",
        description="All services healthy, baseline traffic.",
        duration_hint_seconds=300,
    ),
    "slow_database": ScenarioDefinition(
        name="slow_database",
        label="Slow database",
        description="postgres-db latency spikes; cascades to auth/order services.",
        metric_overrides=[
            MetricOverride("postgres-db", "latency_p95_ms", multiplier=8.0, offset=50.0),
            MetricOverride("postgres-db", "cpu_percent", multiplier=1.7),
            MetricOverride("auth-service", "latency_p95_ms", multiplier=3.0),
            MetricOverride("order-service", "latency_p95_ms", multiplier=3.5),
            MetricOverride("order-service", "error_rate", offset=0.08),
            MetricOverride("api-gateway", "error_rate", offset=0.03),
        ],
        affected_services=["postgres-db", "auth-service", "order-service", "api-gateway"],
        error_log_templates=[
            ("ERROR", "DB query timeout after {ms}ms"),
            ("WARN", "Query slow: {ms}ms on SELECT orders"),
        ],
    ),
    "memory_leak": ScenarioDefinition(
        name="memory_leak",
        label="Order-service memory leak",
        description="order-service memory grows unboundedly until OOM risk.",
        metric_overrides=[
            MetricOverride("order-service", "memory_mb", multiplier=1.0, offset=1200.0),
            MetricOverride("order-service", "cpu_percent", multiplier=1.4),
            MetricOverride("order-service", "latency_p95_ms", multiplier=2.0),
        ],
        affected_services=["order-service"],
        error_log_templates=[
            ("WARN", "Memory usage at {pct}% of limit"),
            ("ERROR", "GC pause exceeded threshold: {ms}ms"),
        ],
    ),
    "cpu_spike": ScenarioDefinition(
        name="cpu_spike",
        label="API gateway CPU spike",
        description="api-gateway CPU pegged; requests queue up, latency rises.",
        metric_overrides=[
            MetricOverride("api-gateway", "cpu_percent", multiplier=2.6, offset=20.0),
            MetricOverride("api-gateway", "latency_p95_ms", multiplier=4.0),
            MetricOverride("frontend", "latency_p95_ms", multiplier=2.5),
            MetricOverride("frontend", "error_rate", offset=0.05),
        ],
        affected_services=["api-gateway", "frontend"],
        error_log_templates=[
            ("WARN", "Request queue depth: {n}"),
            ("ERROR", "Upstream timeout on route {route}"),
        ],
    ),
    "error_cascade": ScenarioDefinition(
        name="error_cascade",
        label="Auth-service error cascade",
        description="auth-service begins failing; failures cascade upstream.",
        metric_overrides=[
            MetricOverride("auth-service", "error_rate", offset=0.45),
            MetricOverride("api-gateway", "error_rate", offset=0.20),
            MetricOverride("frontend", "error_rate", offset=0.15),
        ],
        affected_services=["auth-service", "api-gateway", "frontend"],
        error_log_templates=[
            ("ERROR", "Token verification failed: signature mismatch"),
            ("ERROR", "JWT expired for user_id={user_id}"),
            ("WARN", "Auth backend returned 503"),
        ],
    ),
    "service_outage": ScenarioDefinition(
        name="service_outage",
        label="Payment-service outage",
        description="payment-service returns 100% errors — downstream calls fail.",
        metric_overrides=[
            MetricOverride("payment-service", "error_rate", offset=1.0),
            MetricOverride("payment-service", "requests_per_sec", multiplier=0.1),
            MetricOverride("order-service", "error_rate", offset=0.30),
            MetricOverride("api-gateway", "error_rate", offset=0.10),
        ],
        affected_services=["payment-service", "order-service", "api-gateway"],
        error_log_templates=[
            ("FATAL", "Payment gateway unreachable: connection refused"),
            ("ERROR", "Charge failed for order_id={order_id}"),
        ],
    ),
}