"""Run full evaluation across all scenarios."""
from __future__ import annotations

import time

from sqlalchemy import select

from app.agents.graph import build_graph
from app.evaluation.ground_truth import GROUND_TRUTH
from app.evaluation.metrics import EvaluationReport, ScenarioResult
from app.logging_config import get_logger
from app.storage.database import get_session_factory
from app.storage.models import IngestionRun

logger = get_logger("evaluation.runner")


def _pick_representative_run(session, scenario: str) -> str | None:
    """Return the most recent run_id for a given scenario."""
    row = session.execute(
        select(IngestionRun)
        .where(IngestionRun.scenario == scenario)
        .order_by(IngestionRun.ingested_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.run_id if row else None


def run_evaluation() -> EvaluationReport:
    graph = build_graph()
    SessionLocal = get_session_factory()
    results: list[ScenarioResult] = []

    with SessionLocal() as session:
        for scenario_name, truth in GROUND_TRUTH.items():
            run_id = _pick_representative_run(session, scenario_name)
            if not run_id:
                logger.warning("eval_skip_no_run", scenario=scenario_name)
                continue

            logger.info("eval_scenario_start", scenario=scenario_name, run_id=run_id)
            start = time.perf_counter()
            final_state = graph.invoke({
                "incident_id": f"eval_{scenario_name}",
                "run_id": run_id,
                "scenario": scenario_name,
                "timeline": [],
            })
            elapsed = time.perf_counter() - start

            root_cause = final_state.get("root_cause") or {}
            llm_meta = root_cause.get("llm_meta") or {}

            pred_category = (root_cause.get("category") or "unknown").lower()
            pred_service = root_cause.get("primary_service")
            pred_metric = root_cause.get("primary_metric")

            runbook_ctx = final_state.get("runbook_context") or []
            retrieved_ids = [r.get("runbook_id", "") for r in runbook_ctx]

            category_correct = pred_category == truth.expected_category
            service_correct = pred_service == truth.expected_service
            metric_correct = pred_metric == truth.expected_metric
            overall_correct = category_correct and (
                service_correct if truth.expected_service else True
            )
            runbook_retrieved = (
                truth.expected_runbook in retrieved_ids
                if truth.expected_runbook
                else True
            )

            results.append(ScenarioResult(
                run_id=run_id,
                scenario=scenario_name,
                predicted_category=pred_category,
                predicted_service=pred_service,
                predicted_metric=pred_metric,
                expected_category=truth.expected_category,
                expected_service=truth.expected_service,
                expected_metric=truth.expected_metric,
                expected_runbook=truth.expected_runbook,
                category_correct=category_correct,
                service_correct=service_correct,
                metric_correct=metric_correct,
                overall_correct=overall_correct,
                retrieved_runbook_ids=retrieved_ids,
                runbook_retrieved=runbook_retrieved,
                llm_used=bool(llm_meta.get("used")),
                cost_usd=float(llm_meta.get("cost_usd") or 0.0),
                latency_s=elapsed,
            ))

            logger.info(
                "eval_scenario_done",
                scenario=scenario_name,
                category_correct=category_correct,
                service_correct=service_correct,
            )

    return EvaluationReport(total_scenarios=len(results), results=results)