"""API endpoints for triggering simulations."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from sim.config import SCENARIOS
from sim.models import IncidentScenario, SimulationMetadata
from sim.runner import SimulationRunner

logger = get_logger("api.simulate")
router = APIRouter(prefix="/api/v1/simulate", tags=["simulate"])

_runs: dict[str, dict] = {}


class SimulateRequest(BaseModel):
    scenario: IncidentScenario = IncidentScenario.NORMAL
    duration_seconds: float = Field(default=30.0, ge=1.0, le=3600.0)
    tick_interval_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    seed: int | None = None
    speedup: float = Field(default=1.0, ge=1.0, le=100.0)


class SimulateResponse(BaseModel):
    run_id: str
    status: str
    scenario: IncidentScenario


@router.get("/scenarios")
async def list_scenarios() -> dict:
    return {
        "scenarios": [
            {"name": k, "label": v.label, "description": v.description}
            for k, v in SCENARIOS.items()
        ]
    }


@router.post("/start", response_model=SimulateResponse)
async def start_simulation(req: SimulateRequest) -> SimulateResponse:
    runner = SimulationRunner(
        scenario=req.scenario,
        duration_seconds=req.duration_seconds,
        tick_interval_seconds=req.tick_interval_seconds,
        seed=req.seed,
        speedup=req.speedup,
    )
    run_id = runner.run_id
    _runs[run_id] = {"status": "running", "runner": runner, "result": None}

    async def _execute():
        try:
            loop = asyncio.get_running_loop()
            meta = await loop.run_in_executor(None, runner.run)
            _runs[run_id]["status"] = "completed"
            _runs[run_id]["result"] = meta
        except Exception as e:
            logger.exception("simulation_failed", run_id=run_id)
            _runs[run_id]["status"] = "failed"
            _runs[run_id]["error"] = str(e)

    asyncio.create_task(_execute())
    return SimulateResponse(run_id=run_id, status="running", scenario=req.scenario)


@router.get("/status/{run_id}")
async def get_status(run_id: str) -> dict:
    entry = _runs.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    result: SimulationMetadata | None = entry.get("result")
    return {
        "run_id": run_id,
        "status": entry["status"],
        "error": entry.get("error"),
        "result": result.model_dump(mode="json") if result else None,
    }


@router.post("/stop/{run_id}")
async def stop_simulation(run_id: str) -> dict:
    entry = _runs.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    runner: SimulationRunner = entry["runner"]
    runner.request_stop()
    return {"run_id": run_id, "status": "stopping"}


@router.get("/runs")
async def list_runs() -> dict:
    return {
        "runs": [{"run_id": rid, "status": v["status"]} for rid, v in _runs.items()]
    }