"""Tests for the ingestion pipeline."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.storage import database as db_module
from app.storage import repositories as repo
from app.storage.models import LogRow, MetricRow, SpanRow


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()
    db_module.reset_engine()
    db_module.init_db()
    yield
    get_settings.cache_clear()
    db_module.reset_engine()


@pytest.fixture
def fake_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    for sub in ("metrics", "logs", "traces", "runs"):
        (data_dir / sub).mkdir(parents=True)

    run_id = "run_test_001"
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts_str = ts.isoformat().replace("+00:00", "Z")

    metrics = [
        {"timestamp": ts_str, "service": "api-gateway",
         "metric_name": "cpu_percent", "value": 40.0, "labels": {}},
        {"timestamp": ts_str, "service": "api-gateway",
         "metric_name": "latency_p95_ms", "value": 30.0, "labels": {}},
    ]
    (data_dir / "metrics" / f"{run_id}.jsonl").write_text(
        "\n".join(json.dumps(m) for m in metrics) + "\n"
    )

    logs = [
        {"timestamp": ts_str, "service": "api-gateway", "level": "ERROR",
         "message": "boom", "trace_id": "tr1", "span_id": "sp1", "labels": {}},
    ]
    (data_dir / "logs" / f"{run_id}.jsonl").write_text(
        "\n".join(json.dumps(lg) for lg in logs) + "\n"
    )

    spans = [
        {"timestamp": ts_str, "trace_id": "tr1", "span_id": "sp1",
         "parent_span_id": None, "service": "api-gateway",
         "operation": "route_request", "duration_ms": 20.5,
         "status": "error", "labels": {}},
    ]
    (data_dir / "traces" / f"{run_id}.jsonl").write_text(
        "\n".join(json.dumps(s) for s in spans) + "\n"
    )

    (data_dir / "runs" / f"{run_id}.json").write_text(
        json.dumps({"scenario": "cpu_spike"})
    )
    return data_dir, run_id


def test_ingest_and_idempotent(fresh_db, fake_data_dir):
    data_dir, run_id = fake_data_dir
    from app.pipeline.ingestor import TelemetryIngestor

    ingestor = TelemetryIngestor(data_dir=data_dir)
    SessionLocal = db_module.get_session_factory()

    with SessionLocal() as s:
        result = ingestor.ingest_run(run_id, s)
        assert result is not None
        assert result["metrics"] == 2
        assert result["logs"] == 1
        assert result["spans"] == 1

    with SessionLocal() as s:
        again = ingestor.ingest_run(run_id, s)
        assert again is None
        assert repo.count_rows(s, MetricRow) == 2
        assert repo.count_rows(s, LogRow) == 1
        assert repo.count_rows(s, SpanRow) == 1


def test_query_metric_series(fresh_db, fake_data_dir):
    data_dir, run_id = fake_data_dir
    from app.pipeline.ingestor import TelemetryIngestor

    ingestor = TelemetryIngestor(data_dir=data_dir)
    SessionLocal = db_module.get_session_factory()
    with SessionLocal() as s:
        ingestor.ingest_run(run_id, s)

    with SessionLocal() as s:
        rows = repo.query_metric_series(
            s, service="api-gateway", metric_name="cpu_percent", run_id=run_id
        )
        assert len(rows) == 1
        assert rows[0].value == 40.0


def test_query_logs_and_traces(fresh_db, fake_data_dir):
    data_dir, run_id = fake_data_dir
    from app.pipeline.ingestor import TelemetryIngestor

    ingestor = TelemetryIngestor(data_dir=data_dir)
    SessionLocal = db_module.get_session_factory()
    with SessionLocal() as s:
        ingestor.ingest_run(run_id, s)

    with SessionLocal() as s:
        logs = repo.query_logs(s, level="ERROR", run_id=run_id)
        assert len(logs) == 1
        assert logs[0].message == "boom"

        roots = repo.list_recent_traces(s, run_id=run_id)
        assert len(roots) == 1
        assert roots[0].status == "error"

        spans = repo.get_trace_spans(s, "tr1")
        assert len(spans) == 1