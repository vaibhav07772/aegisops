"""Tests for the LangGraph agent orchestration.

These tests run in RULE-BASED mode (USE_LLM_REASONER=false) to ensure
deterministic behavior. LLM path is tested separately in test_llm.py.
RAG is disabled (RAG_ENABLED=false) to avoid model downloads in tests.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agents.graph import build_graph
from app.config import get_settings
from app.storage import database as db_module
from app.storage.models import IngestionRun, LogRow, MetricRow, SpanRow


def _fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_agents.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("USE_LLM_REASONER", "false")  # force deterministic rule-based
    monkeypatch.setenv("RAG_ENABLED", "false")       # skip RAG (no model download)
    get_settings.cache_clear()
    db_module.reset_engine()
    db_module.init_db()
    return db_module.get_session_factory()


@pytest.fixture
def seeded_db_memory_leak(tmp_path, monkeypatch):
    SessionLocal = _fresh_db(tmp_path, monkeypatch)
    ts = datetime(2026, 1, 1, 12, 0, 0)
    with SessionLocal() as s:
        s.add(IngestionRun(
            run_id="run_leak", scenario="memory_leak", ingested_at=ts,
            metrics_count=4, logs_count=1, spans_count=2,
        ))
        for val in [400.0, 800.0, 1200.0, 1600.0]:
            s.add(MetricRow(
                run_id="run_leak", timestamp=ts, service="order-service",
                metric_name="memory_mb", value=val,
            ))
        s.add(LogRow(
            run_id="run_leak", timestamp=ts, service="order-service",
            level="ERROR", message="OOM risk", trace_id=None, span_id=None,
        ))
        s.add(SpanRow(
            run_id="run_leak", timestamp=ts, trace_id="tr1", span_id="sp1",
            parent_span_id=None, service="order-service",
            operation="create_order", duration_ms=5200.0, status="error",
        ))
        s.add(SpanRow(
            run_id="run_leak", timestamp=ts, trace_id="tr2", span_id="sp2",
            parent_span_id=None, service="order-service",
            operation="list_orders", duration_ms=300.0, status="ok",
        ))
        s.commit()
    yield
    get_settings.cache_clear()
    db_module.reset_engine()


@pytest.fixture
def seeded_db_normal(tmp_path, monkeypatch):
    SessionLocal = _fresh_db(tmp_path, monkeypatch)
    ts = datetime(2026, 1, 1, 12, 0, 0)
    with SessionLocal() as s:
        s.add(IngestionRun(
            run_id="run_norm", scenario="normal", ingested_at=ts,
            metrics_count=4, logs_count=0, spans_count=1,
        ))
        for val in [200.0, 205.0, 202.0, 210.0]:
            s.add(MetricRow(
                run_id="run_norm", timestamp=ts, service="api-gateway",
                metric_name="memory_mb", value=val,
            ))
        for val in [0.001, 0.002, 0.003, 0.002]:
            s.add(MetricRow(
                run_id="run_norm", timestamp=ts, service="api-gateway",
                metric_name="error_rate", value=val,
            ))
        s.add(SpanRow(
            run_id="run_norm", timestamp=ts, trace_id="tr1", span_id="sp1",
            parent_span_id=None, service="api-gateway",
            operation="route_request", duration_ms=30.0, status="ok",
        ))
        s.commit()
    yield
    get_settings.cache_clear()
    db_module.reset_engine()


@pytest.fixture
def seeded_db_slow_db(tmp_path, monkeypatch):
    SessionLocal = _fresh_db(tmp_path, monkeypatch)
    ts = datetime(2026, 1, 1, 12, 0, 0)
    with SessionLocal() as s:
        s.add(IngestionRun(
            run_id="run_slowdb", scenario="slow_database", ingested_at=ts,
            metrics_count=0, logs_count=0, spans_count=0,
        ))
        for val in [15.0, 20.0, 180.0, 175.0]:
            s.add(MetricRow(
                run_id="run_slowdb", timestamp=ts, service="postgres-db",
                metric_name="latency_p95_ms", value=val,
            ))
        for val in [0.001, 0.001, 0.001, 0.001]:
            s.add(MetricRow(
                run_id="run_slowdb", timestamp=ts, service="auth-service",
                metric_name="error_rate", value=val,
            ))
        s.commit()
    yield
    get_settings.cache_clear()
    db_module.reset_engine()


def _run(graph, run_id, scenario):
    return graph.invoke({
        "incident_id": f"inc_{run_id}",
        "run_id": run_id,
        "scenario": scenario,
        "timeline": [],
    })


def test_memory_leak_detected(seeded_db_memory_leak):
    graph = build_graph()
    result = _run(graph, "run_leak", "memory_leak")

    rc = result["root_cause"]
    assert rc["category"] == "memory"
    assert rc["primary_service"] == "order-service"
    assert rc["severity"] >= 2.5
    assert rc["confidence"] == "high"

    rem = result["remediation"]
    assert rem["action"] == "restart_service"
    assert rem["target_service"] == "order-service"
    assert rem["requires_approval"] is True

    timeline_agents = {entry["agent"] for entry in result["timeline"]}
    assert {
        "supervisor", "metric_agent", "log_agent", "trace_agent",
        "reasoner", "remediation_agent",
    }.issubset(timeline_agents)


def test_normal_returns_healthy(seeded_db_normal):
    graph = build_graph()
    result = _run(graph, "run_norm", "normal")

    rc = result["root_cause"]
    assert rc["category"] == "healthy", f"expected healthy, got {rc}"
    assert rc["primary_service"] is None
    assert rc["severity"] < 0.5

    rem = result["remediation"]
    assert rem["action"] == "no_action"
    assert rem["requires_approval"] is False


def test_slow_database_picks_latency_not_error_rate(seeded_db_slow_db):
    graph = build_graph()
    result = _run(graph, "run_slowdb", "slow_database")

    rc = result["root_cause"]
    assert rc["category"] == "latency", f"got {rc}"
    assert rc["primary_service"] == "postgres-db"
    assert rc["primary_metric"] == "latency_p95_ms"


def test_empty_run_does_not_crash(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)

    graph = build_graph()
    result = _run(graph, "nonexistent", "unknown")

    assert result.get("root_cause") is not None
    assert result["root_cause"]["category"] == "healthy"
    assert result.get("remediation") is not None
    assert result["remediation"]["action"] == "no_action"

    get_settings.cache_clear()
    db_module.reset_engine()