"""Prometheus metrics for AegisOps."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# === HTTP / API ===
http_requests_total = Counter(
    "aegisops_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "aegisops_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# === Anomaly Detection ===
anomalies_detected_total = Counter(
    "aegisops_anomalies_detected_total",
    "Total anomalies detected",
    ["severity"],
)

anomaly_score = Gauge(
    "aegisops_anomaly_score",
    "Latest anomaly score",
    ["service"],
)

# === Incidents ===
incidents_total = Counter(
    "aegisops_incidents_total",
    "Total incidents created",
    ["severity", "status"],
)

incident_resolution_seconds = Histogram(
    "aegisops_incident_resolution_seconds",
    "Time to resolve an incident (MTTR)",
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
)

# === Agent Activity ===
agent_invocations_total = Counter(
    "aegisops_agent_invocations_total",
    "Agent invocations",
    ["agent_name", "status"],
)

agent_duration_seconds = Histogram(
    "aegisops_agent_duration_seconds",
    "Agent execution duration",
    ["agent_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

llm_tokens_total = Counter(
    "aegisops_llm_tokens_total",
    "Total LLM tokens used",
    ["model", "type"],  # type = input / output
)

llm_cost_usd_total = Counter(
    "aegisops_llm_cost_usd_total",
    "Cumulative LLM cost in USD",
    ["model"],
)

# === LLM Cache ===
llm_cache_total = Counter(
    "aegisops_llm_cache_total",
    "Semantic cache results",
    ["result"],  # hit / miss / miss_expired
)

# === Guardrails ===
guardrail_blocks_total = Counter(
    "aegisops_guardrail_blocks_total",
    "Total guardrail blocks",
    ["guardrail_type"],  # pii / injection / dangerous_cmd / permission
)

# === RAG ===
rag_retrieval_seconds = Histogram(
    "aegisops_rag_retrieval_seconds",
    "RAG retrieval latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

llm_request_duration_seconds = Histogram(
    "aegisops_llm_request_duration_seconds",
    "LLM request duration",
    ["model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

llm_errors_total = Counter(
    "aegisops_llm_errors_total",
    "LLM errors",
    ["model", "error_type"],
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST