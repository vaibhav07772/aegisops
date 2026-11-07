"""One-shot bootstrap for fresh Docker containers (idempotent).

Runs on API startup:
  1. init DB tables
  2. create runbook files if missing
  3. ingest runbooks into ChromaDB if empty
  4. generate + ingest simulation data if DB has no runs
  5. train anomaly baseline model if missing
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("docker.bootstrap")
settings = get_settings()


def step_init_db() -> None:
    from app.storage.database import init_db
    init_db()
    logger.info("bootstrap_db_ready")


def step_setup_runbook_files() -> None:
    runbooks_dir = settings.runbooks_dir
    runbooks_dir.mkdir(parents=True, exist_ok=True)
    existing = list(runbooks_dir.glob("*.md"))
    if existing:
        logger.info("bootstrap_runbook_files_exist", count=len(existing))
        return
    logger.info("bootstrap_runbook_files_creating")
    from scripts.setup_runbooks import RUNBOOKS
    for name, content in RUNBOOKS.items():
        (runbooks_dir / f"{name}.md").write_text(content, encoding="utf-8")
    logger.info("bootstrap_runbook_files_created", count=len(RUNBOOKS))


def step_ingest_runbooks() -> None:
    from app.rag.retriever import get_retriever
    r = get_retriever()
    if r.is_ingested():
        logger.info("bootstrap_runbooks_already_ingested")
        return
    logger.info("bootstrap_runbooks_ingesting")
    r.ingest(force=False)


def step_generate_data_if_empty() -> None:
    from sqlalchemy import select
    from app.storage.database import get_session_factory
    from app.storage.models import IngestionRun

    SessionLocal = get_session_factory()
    with SessionLocal() as s:
        has_runs = s.execute(select(IngestionRun).limit(1)).first() is not None

    if has_runs:
        logger.info("bootstrap_data_exists")
        return

    logger.info("bootstrap_data_generating")
    from sim.runner import SimulationRunner
    from sim.models import IncidentScenario
    from app.pipeline.ingestor import TelemetryIngestor

    scenarios = [
        "normal", "memory_leak", "slow_database",
        "service_outage", "cpu_spike", "error_cascade",
    ]
    for name in scenarios:
        logger.info("bootstrap_sim_running", scenario=name)
        SimulationRunner(
            scenario=IncidentScenario(name),
            duration_seconds=30.0,
            tick_interval_seconds=1.0,
            speedup=10.0,
        ).run()

    with SessionLocal() as s:
        TelemetryIngestor().ingest_all(s)
    logger.info("bootstrap_data_ingested")


def step_train_model_if_missing() -> None:
    model_path = settings.models_dir / "anomaly_detector.pkl"
    if model_path.exists():
        logger.info("bootstrap_model_exists")
        return
    logger.info("bootstrap_model_training")
    try:
        from scripts.train_anomaly import main as train_main
        train_main()
    except Exception:
        logger.exception("bootstrap_model_training_failed")


def main() -> None:
    logger.info("bootstrap_start")
    step_init_db()
    step_setup_runbook_files()
    step_ingest_runbooks()
    step_generate_data_if_empty()
    step_train_model_if_missing()
    logger.info("bootstrap_complete")


if __name__ == "__main__":
    main()