"""LLM-powered reasoner node with fallback to rule-based."""
from __future__ import annotations

from app.agents.nodes.reasoner import _pick_root_cause
from app.agents.state import IncidentState
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import (
    PROMPT_VERSION_REASONER,
    REASONER_SYSTEM,
    build_reasoner_prompt,
)
from app.llm.schemas import LLMRootCause
from app.logging_config import get_logger

logger = get_logger("agents.reasoner_llm")

_client = LLMClient()

# Enforce 1:1 mapping between category and primary_metric
CATEGORY_TO_METRIC = {
    "cpu": "cpu_percent",
    "memory": "memory_mb",
    "latency": "latency_p95_ms",
    "errors": "error_rate",
    "traffic": "requests_per_sec",
}


def _infer_category_from_metric(metric: str) -> str:
    m = (metric or "").lower()
    if "memory" in m:
        return "memory"
    if "error" in m:
        return "errors"
    if "latency" in m:
        return "latency"
    if "cpu" in m:
        return "cpu"
    if "request" in m or "traffic" in m:
        return "traffic"
    return "unknown"


def _resolve_category(llm: LLMRootCause) -> str:
    """If LLM omitted/invalidated category, infer from primary_metric or candidates."""
    if llm.category and llm.category != "unknown":
        return llm.category
    if llm.primary_metric:
        inferred = _infer_category_from_metric(llm.primary_metric)
        if inferred != "unknown":
            return inferred
    for c in llm.candidates:
        inferred = _infer_category_from_metric(c.metric)
        if inferred != "unknown":
            return inferred
    return "unknown"


def reasoner_llm_node(state: IncidentState) -> dict:
    metric_findings = state.get("metric_findings", {})
    log_findings = state.get("log_findings", {})
    trace_findings = state.get("trace_findings", {})
    runbook_context = state.get("runbook_context")

    llm_meta: dict = {"used": False}

    if _client.is_available:
        try:
            prompt = build_reasoner_prompt(
                metric_findings,
                log_findings,
                trace_findings,
                runbook_context=runbook_context,
            )
            result, usage = _client.complete_structured(
                prompt=prompt,
                schema=LLMRootCause,
                system_prompt=REASONER_SYSTEM,
                prompt_version=PROMPT_VERSION_REASONER,
            )
            root_cause = _normalize_llm_root_cause(
                result, metric_findings, log_findings, trace_findings
            )
            llm_meta = {"used": True, **usage}
            logger.info("reasoner_llm_success", **llm_meta)
        except (LLMError, Exception) as e:  # noqa: BLE001
            logger.warning("reasoner_llm_fallback", error=str(e)[:200])
            root_cause = _pick_root_cause(
                metric_findings, log_findings, trace_findings
            )
            llm_meta = {"used": False, "fallback_reason": str(e)[:200]}
    else:
        logger.info("reasoner_llm_disabled_no_api_key")
        root_cause = _pick_root_cause(metric_findings, log_findings, trace_findings)

    root_cause["llm_meta"] = llm_meta
    return {
        "root_cause": root_cause,
        "timeline": [
            {
                "agent": "reasoner",
                "action": "hypothesized_root_cause",
                "category": root_cause.get("category"),
                "severity": root_cause.get("severity"),
                "confidence": root_cause.get("confidence"),
                "llm_used": llm_meta.get("used", False),
            }
        ],
    }


def _normalize_llm_root_cause(
    llm: LLMRootCause,
    metric_findings: dict,
    log_findings: dict,
    trace_findings: dict,
) -> dict:
    category = _resolve_category(llm)

    error_logs = log_findings.get("by_level", {}).get("ERROR", 0)
    fatal_logs = log_findings.get("by_level", {}).get("FATAL", 0)
    error_spans = trace_findings.get("error_by_service", {})
    reinforced = (
        llm.primary_service is not None
        and error_spans.get(llm.primary_service, 0) > 0
    )

    # Healthy path
    if category == "healthy" or (llm.severity == 0 and not llm.primary_service):
        return {
            "hypothesis": llm.hypothesis or "No significant anomaly detected",
            "primary_service": None,
            "primary_metric": None,
            "category": "healthy",
            "confidence": llm.confidence,
            "severity": 0.3,
            "reinforced_by_traces": False,
            "error_logs": error_logs,
            "fatal_logs": fatal_logs,
            "candidates": [],
            "evidence": {
                "top_severity": 0.3,
                "llm_evidence": llm.evidence_summary,
            },
        }

    # Anomaly path
    series = metric_findings.get("series", {})
    
    # --- Normalization: Enforce category-metric consistency ---
    # If LLM picked 'cpu' but metric 'latency_p95_ms', force it to 'cpu_percent'
    if category in CATEGORY_TO_METRIC:
        expected_metric = CATEGORY_TO_METRIC[category]
        if llm.primary_metric != expected_metric:
            logger.warning(
                "metric_mismatch_corrected",
                expected=expected_metric,
                got=llm.primary_metric,
                category=category,
            )
            llm.primary_metric = expected_metric

    key = f"{llm.primary_service}::{llm.primary_metric}"
    primary_s = series.get(key, {})

    candidates = [
        {
            "service": c.service,
            "metric": c.metric,
            "category": _infer_category_from_metric(c.metric),
            "severity": c.severity,
            "baseline_ratio": c.baseline_ratio,
            "hypothesis": c.reason,
        }
        for c in llm.candidates
    ]

    return {
        "hypothesis": llm.hypothesis,
        "primary_service": llm.primary_service,
        "primary_metric": llm.primary_metric,
        "category": category,
        "confidence": llm.confidence,
        "severity": float(llm.severity),
        "reinforced_by_traces": reinforced,
        "error_logs": error_logs,
        "fatal_logs": fatal_logs,
        "candidates": candidates,
        "evidence": {
            "primary_severity": float(llm.severity),
            "primary_baseline_ratio": primary_s.get("baseline_ratio"),
            "error_spans_on_service": error_spans.get(llm.primary_service, 0),
            "llm_evidence": llm.evidence_summary,
        },
    }