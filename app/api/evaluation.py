"""Evaluation API — run full eval, get report."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.evaluation.runner import run_evaluation
from app.logging_config import get_logger

logger = get_logger("api.evaluation")
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.post("/run")
def run_full_evaluation() -> dict:
    """Run evaluation across all 6 scenarios and return metrics."""
    logger.info("evaluation_started")
    try:
        report = run_evaluation()
    except Exception as e:
        logger.exception("evaluation_failed")
        raise HTTPException(500, f"Evaluation failed: {e}") from e
    logger.info(
        "evaluation_completed",
        total=report.total_scenarios,
        overall=report.overall_accuracy,
    )
    return report.to_dict()


@router.get("/health")
def evaluation_health() -> dict:
    return {"status": "ready", "scenarios": 6, "metrics": [
        "category_accuracy", "service_accuracy", "metric_accuracy",
        "overall_accuracy", "rag_precision", "cost_usd", "latency_s",
    ]}