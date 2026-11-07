"""RunbookAgent — retrieves relevant runbook chunks via hybrid RAG."""
from __future__ import annotations

from app.agents.state import IncidentState
from app.config import get_settings
from app.logging_config import get_logger
from app.rag.retriever import get_retriever

logger = get_logger("agents.runbook")

# Semantic hints per category — anchors RAG retrieval to correct runbook
CATEGORY_HINTS = {
    "cpu": "cpu saturation high CPU usage runaway process overload",
    "memory": "memory leak growing memory unbounded allocation OOM",
    "latency": "slow database high latency query timeout connection pool",
    "errors": "service outage errors failing requests connection refused",
    "traffic": "traffic spike request rate sudden load",
}


def _detect_categories(series: dict[str, dict]) -> list[str]:
    """Detect candidate categories via absolute thresholds."""
    cats: list[str] = []
    for s in series.values():
        metric = s.get("metric", "")
        max_v = float(s.get("max", 0.0))
        ratio = float(s.get("baseline_ratio") or 0.0)

        if metric == "cpu_percent" and max_v >= 90 and "cpu" not in cats:
            cats.append("cpu")
        if metric == "memory_mb" and ratio >= 2.5 and "memory" not in cats:
            cats.append("memory")
        if metric == "error_rate" and max_v >= 0.20 and "errors" not in cats:
            cats.append("errors")
        if metric == "latency_p95_ms" and ratio >= 5.0 and "latency" not in cats:
            cats.append("latency")
    return cats


def _build_query(state: IncidentState) -> str:
    metric_f = state.get("metric_findings", {}) or {}
    trace_f = state.get("trace_findings", {}) or {}

    series = metric_f.get("series", {})

    # 1. Semantic category hints (drive retrieval)
    hints: list[str] = []
    for cat in _detect_categories(series):
        hints.append(CATEGORY_HINTS[cat])
    hint_block = " | ".join(hints)

    # 2. Top 3 by baseline_ratio
    top_by_ratio = sorted(
        series.values(),
        key=lambda s: (s.get("baseline_ratio") or 0, s.get("max", 0)),
        reverse=True,
    )[:3]

    parts: list[str] = []
    if hint_block:
        parts.append(hint_block)
    for s in top_by_ratio:
        parts.append(
            f"{s['service']} {s['metric']} "
            f"ratio {s.get('baseline_ratio')}x max {s.get('max')}"
        )
    if trace_f.get("error_by_service"):
        parts.append(f"error spans: {list(trace_f['error_by_service'].keys())}")

    return " | ".join(parts) or "general incident"


def runbook_agent_node(state: IncidentState) -> dict:
    settings = get_settings()

    if not settings.rag_enabled:
        return {
            "runbook_context": [],
            "timeline": [{"agent": "runbook_agent", "action": "disabled"}],
        }

    try:
        retriever = get_retriever()
        if not retriever.is_ingested():
            return {
                "runbook_context": [],
                "timeline": [{"agent": "runbook_agent", "action": "not_ingested"}],
            }

        query = _build_query(state)
        hits = retriever.search(query, top_k=3)

        runbook_context = [
            {
                "runbook_id": h.runbook_id,
                "title": h.title,
                "section": h.section,
                "content": h.content,
                "score": round(h.score, 3),
            }
            for h in hits
        ]

        logger.info(
            "runbook_agent_complete",
            query=query[:200],
            hits=len(runbook_context),
        )
        return {
            "runbook_context": runbook_context,
            "timeline": [
                {
                    "agent": "runbook_agent",
                    "action": "retrieved_runbooks",
                    "hits": len(runbook_context),
                }
            ],
        }
    except Exception as e:
        logger.exception("runbook_agent_failed")
        return {
            "runbook_context": [],
            "timeline": [
                {"agent": "runbook_agent", "action": "failed", "error": str(e)[:200]}
            ],
        }