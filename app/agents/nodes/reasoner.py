"""Reasoner — combines findings into a root-cause hypothesis.

Uses two severity signals:
1. Absolute thresholds (CPU > 90%, error_rate > 10%, etc.)
2. Baseline-relative ratio (run mean / historical baseline mean) — catches
   "constantly-elevated" anomalies (e.g., DB latency at 170ms vs 15ms baseline).
"""
from __future__ import annotations

from app.agents.state import IncidentState
from app.logging_config import get_logger

logger = get_logger("agents.reasoner")

SEVERITY_HEALTHY = 0.5
SEVERITY_CRITICAL = 2.5


def _growth(min_v: float, max_v: float) -> float:
    eps = max(1e-6, 0.01 * abs(max_v))
    denom = max(abs(min_v), eps)
    return max_v / denom if denom > 0 else 1.0


def _severity_absolute(metric: str, s: dict) -> float:
    """Within-run absolute threshold check."""
    max_v = s.get("max", 0.0)
    min_v = s.get("min", 0.0)

    if metric == "error_rate":
        if max_v >= 0.10:
            return 3.0
        if max_v >= 0.05:
            return 2.0
        if max_v >= 0.02:
            return 1.0
        return 0.1

    if metric == "cpu_percent":
        if max_v >= 90:
            return 3.0
        if max_v >= 80:
            return 2.0
        if max_v >= 70:
            return 1.0
        return 0.1

    if metric == "memory_mb":
        g = _growth(min_v, max_v)
        if g >= 3.0:
            return 3.0
        if g >= 2.0:
            return 2.0
        if g >= 1.5:
            return 1.0
        return 0.1

    if metric == "latency_p95_ms":
        g = _growth(min_v, max_v)
        if g >= 4.0:
            return 3.0
        if g >= 2.5:
            return 2.0
        if g >= 1.7:
            return 1.0
        return 0.1

    if metric == "requests_per_sec":
        return 0.3

    return 0.1


def _severity_baseline(s: dict) -> float:
    """Baseline-relative severity (run mean vs historical normal mean)."""
    ratio = s.get("baseline_ratio")
    if not ratio or ratio < 1.5:
        return 0.0
    if ratio >= 5.0:
        return 3.0
    if ratio >= 2.5:
        return 2.0
    return 1.0


def _severity(metric: str, s: dict) -> float:
    return max(_severity_absolute(metric, s), _severity_baseline(s))


def _tiebreak_score(metric: str, s: dict) -> float:
    if metric == "error_rate":
        return float(s.get("max", 0.0))
    growth = _growth(s.get("min", 0.0), s.get("max", 0.0))
    baseline_ratio = s.get("baseline_ratio") or 0.0
    return max(growth, baseline_ratio)


def _hypothesis_for(metric: str, s: dict) -> tuple[str, str]:
    service = s["service"]
    max_v = s["max"]
    min_v = s["min"]
    g = _growth(min_v, max_v)
    baseline_mean = s.get("baseline_mean")
    baseline_ratio = s.get("baseline_ratio")

    baseline_tag = ""
    if baseline_ratio and baseline_ratio >= 1.5:
        baseline_tag = f" — {baseline_ratio:.1f}× normal baseline ({baseline_mean:.0f})"

    if metric == "memory_mb":
        return (
            "memory",
            f"Memory issue on {service} "
            f"({min_v:.0f} → {max_v:.0f} MB, {g:.1f}× growth){baseline_tag}",
        )
    if metric == "error_rate":
        return (
            "errors",
            f"Elevated error rate on {service} (peak {max_v:.2%}){baseline_tag}",
        )
    if metric == "latency_p95_ms":
        return (
            "latency",
            f"High latency on {service} "
            f"(peak {max_v:.0f} ms, {g:.1f}× growth){baseline_tag}",
        )
    if metric == "cpu_percent":
        return (
            "cpu",
            f"CPU saturation on {service} (peak {max_v:.1f}%){baseline_tag}",
        )
    if metric == "requests_per_sec":
        return (
            "traffic",
            f"Traffic anomaly on {service} ({min_v:.0f}-{max_v:.0f} rps){baseline_tag}",
        )
    return ("unknown", f"Volatility on {service}::{metric}")


def _pick_root_cause(metric_findings, log_findings, trace_findings) -> dict:
    series = metric_findings.get("series", {})

    scored: list[tuple[float, float, str, dict, str, str]] = []
    for key, s in series.items():
        sev = _severity(s["metric"], s)
        tb = _tiebreak_score(s["metric"], s)
        cat, hyp = _hypothesis_for(s["metric"], s)
        scored.append((sev, tb, key, s, cat, hyp))

    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    top_severity = scored[0][0] if scored else 0.0

    # ---- HEALTHY ----
    if top_severity < SEVERITY_HEALTHY:
        return {
            "hypothesis": "No significant anomaly detected — system operating within normal bounds",
            "primary_service": None,
            "primary_metric": None,
            "category": "healthy",
            "confidence": "high",
            "severity": round(top_severity, 2),
            "reinforced_by_traces": False,
            "error_logs": log_findings.get("by_level", {}).get("ERROR", 0),
            "fatal_logs": log_findings.get("by_level", {}).get("FATAL", 0),
            "candidates": [],
            "evidence": {"top_severity": round(top_severity, 2)},
        }

    # ---- ANOMALY ----
    primary_sev, primary_tb, _pk, primary_s, category, hypothesis = scored[0]
    primary_service = primary_s["service"]
    primary_metric = primary_s["metric"]

    error_spans = trace_findings.get("error_by_service", {})
    error_logs = log_findings.get("by_level", {}).get("ERROR", 0)
    fatal_logs = log_findings.get("by_level", {}).get("FATAL", 0)
    reinforced = bool(primary_service in error_spans and error_spans.get(primary_service, 0) > 0)

    if primary_sev >= SEVERITY_CRITICAL:
        confidence = "high"
    elif primary_sev >= 1.5 and reinforced:
        confidence = "high"
    elif primary_sev >= 1.5 or reinforced:
        confidence = "medium"
    else:
        confidence = "low"

    candidates = [
        {
            "service": s["service"],
            "metric": s["metric"],
            "category": cat,
            "severity": round(sev, 2),
            "tiebreak": round(tb, 3),
            "baseline_ratio": s.get("baseline_ratio"),
            "hypothesis": hyp,
        }
        for sev, tb, _k, s, cat, hyp in scored[:5]
        if sev >= SEVERITY_HEALTHY
    ]

    return {
        "hypothesis": hypothesis,
        "primary_service": primary_service,
        "primary_metric": primary_metric,
        "category": category,
        "confidence": confidence,
        "severity": round(primary_sev, 2),
        "reinforced_by_traces": reinforced,
        "error_logs": error_logs,
        "fatal_logs": fatal_logs,
        "candidates": candidates,
        "evidence": {
            "primary_severity": round(primary_sev, 2),
            "primary_tiebreak": round(primary_tb, 3),
            "primary_baseline_ratio": primary_s.get("baseline_ratio"),
            "error_spans_on_service": error_spans.get(primary_service, 0),
        },
    }


def reasoner_node(state: IncidentState) -> dict:
    root_cause = _pick_root_cause(
        state.get("metric_findings", {}),
        state.get("log_findings", {}),
        state.get("trace_findings", {}),
    )
    logger.info(
        "reasoner_complete",
        category=root_cause.get("category"),
        severity=root_cause.get("severity"),
        confidence=root_cause.get("confidence"),
        target=root_cause.get("primary_service"),
    )
    return {
        "root_cause": root_cause,
        "timeline": [
            {
                "agent": "reasoner",
                "action": "hypothesized_root_cause",
                "category": root_cause.get("category"),
                "severity": root_cause.get("severity"),
                "confidence": root_cause.get("confidence"),
            }
        ],
    }