"""MetricAgent — aggregates metrics for a run, with baseline comparison."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from functools import lru_cache

from sqlalchemy import select

from app.agents.state import IncidentState
from app.config import get_settings
from app.logging_config import get_logger
from app.storage.database import get_session_factory
from app.storage.models import MetricRow

logger = get_logger("agents.metric")


@lru_cache(maxsize=1)
def _load_baseline_means() -> dict[str, float]:
    """Load per-(service::metric) baseline means from trained model."""
    try:
        path = get_settings().models_dir / "baseline.json"
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {k: float(v["mean"]) for k, v in payload.items()}
    except Exception:
        logger.exception("baseline_load_failed")
        return {}


def metric_agent_node(state: IncidentState) -> dict:
    run_id = state["run_id"]
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        rows = session.execute(
            select(
                MetricRow.timestamp,
                MetricRow.service,
                MetricRow.metric_name,
                MetricRow.value,
            ).where(MetricRow.run_id == run_id)
        ).all()

    if not rows:
        return {
            "metric_findings": {"series": {}, "total_series": 0},
            "timeline": [{"agent": "metric_agent", "action": "no_metrics_found"}],
        }

    baseline_means = _load_baseline_means()

    agg: dict[tuple[str, str], list[float]] = defaultdict(list)
    for _ts, svc, metric, val in rows:
        agg[(svc, metric)].append(float(val))

    summary: dict[str, dict] = {}
    for (svc, metric), values in agg.items():
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        key = f"{svc}::{metric}"
        baseline_mean = baseline_means.get(key)
        baseline_ratio = (mean / baseline_mean) if baseline_mean and baseline_mean > 1e-6 else None

        summary[key] = {
            "service": svc,
            "metric": metric,
            "count": len(values),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "baseline_mean": round(baseline_mean, 4) if baseline_mean else None,
            "baseline_ratio": round(baseline_ratio, 3) if baseline_ratio else None,
        }

    logger.info("metric_agent_complete", run_id=run_id, series_count=len(summary))
    return {
        "metric_findings": {
            "series": summary,
            "total_series": len(summary),
            "total_points": len(rows),
        },
        "timeline": [
            {
                "agent": "metric_agent",
                "action": "aggregated_metrics",
                "series": len(summary),
                "points": len(rows),
            }
        ],
    }