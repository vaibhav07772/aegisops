"""Agent orchestration API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.logging_config import get_logger
from app.storage.database import get_session
from app.storage.models import IngestionRun

logger = get_logger("api.agents")
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("graph_compiled")
    return _graph


class AnalysisResponse(BaseModel):
    incident_id: str
    run_id: str
    scenario: str
    root_cause: dict | None = None
    remediation: dict | None = None
    timeline: list[dict]
    metric_series_count: int = 0
    log_patterns_count: int = 0
    trace_error_count: int = 0
    llm_meta: dict | None = None


@router.post("/analyze/{run_id}", response_model=AnalysisResponse)
def analyze_run(run_id: str, session: Session = Depends(get_session)) -> AnalysisResponse:
    run = session.query(IngestionRun).filter_by(run_id=run_id).first()
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")

    graph = get_graph()
    initial_state = {
        "incident_id": f"inc_{run_id[:12]}",
        "run_id": run_id,
        "scenario": run.scenario,
        "timeline": [],
    }

    logger.info("analysis_started", run_id=run_id, scenario=run.scenario)
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        logger.exception("analysis_failed", run_id=run_id)
        raise HTTPException(500, f"Analysis failed: {e}") from e

    metric_findings = final_state.get("metric_findings", {}) or {}
    log_findings = final_state.get("log_findings", {}) or {}
    trace_findings = final_state.get("trace_findings", {}) or {}

    logger.info(
        "analysis_completed",
        run_id=run_id,
        confidence=(final_state.get("root_cause") or {}).get("confidence"),
        action=(final_state.get("remediation") or {}).get("action"),
        llm_used=(final_state.get("root_cause") or {}).get("llm_meta", {}).get("used", False),
    )

    response = AnalysisResponse(
        incident_id=initial_state["incident_id"],
        run_id=run_id,
        scenario=run.scenario,
        root_cause=final_state.get("root_cause"),
        remediation=final_state.get("remediation"),
        timeline=final_state.get("timeline", []),
        metric_series_count=metric_findings.get("total_series", 0),
        log_patterns_count=len(log_findings.get("top_patterns", [])),
        trace_error_count=len(trace_findings.get("error_spans", [])),
        llm_meta=(final_state.get("root_cause") or {}).get("llm_meta"),
    )

    # Persist incident for human-in-loop review (non-fatal)
    try:
        from app.storage import incidents as incident_repo

        incident_repo.upsert_from_analysis(
            session,
            incident_id=response.incident_id,
            run_id=run_id,
            scenario=run.scenario,
            analysis=response.model_dump(mode="json"),
        )
        session.commit()
        logger.info("incident_saved", incident_id=response.incident_id)
    except Exception:
        session.rollback()
        logger.exception("incident_save_failed", incident_id=response.incident_id)

    return response


@router.get("/health")
def agents_health() -> dict:
    graph = get_graph()
    return {
        "status": "ready",
        "graph_nodes": 6,
        "pattern": "supervisor + 5 agents",
        "nodes": [
            "supervisor",
            "metric_agent",
            "log_agent",
            "trace_agent",
            "reasoner",
            "remediation_agent",
        ],
    }