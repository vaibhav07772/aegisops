"""Tests for LLM integration + fallback behavior."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agents.graph import build_graph
from app.agents.nodes import reasoner_llm as rlm
from app.agents.nodes import remediation_llm as remlm
from app.config import get_settings
from app.llm.client import LLMError
from app.llm.schemas import (
    LLMCandidate,
    LLMRemediation,
    LLMRemediationStep,
    LLMRootCause,
)
from app.storage import database as db_module
from app.storage.models import IngestionRun, LogRow, MetricRow, SpanRow


# ---------- Fixtures ----------

def _fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_llm.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("RAG_ENABLED", "false")  # skip RAG (no model download)
    get_settings.cache_clear()
    db_module.reset_engine()
    db_module.init_db()
    return db_module.get_session_factory()


@pytest.fixture
def seeded_memory_leak(tmp_path, monkeypatch):
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


class _FakeClientSuccess:
    is_available = True

    def __init__(self, root_cause: LLMRootCause, remediation: LLMRemediation):
        self._rc = root_cause
        self._rem = remediation

    def complete_structured(self, *, prompt, schema, system_prompt=None, prompt_version="v1"):
        if schema is LLMRootCause:
            return self._rc, {
                "model": "mock-llama", "input_tokens": 100, "output_tokens": 50,
                "total_tokens": 150, "cost_usd": 0.0001, "latency_s": 0.5,
                "prompt_version": prompt_version,
            }
        if schema is LLMRemediation:
            return self._rem, {
                "model": "mock-llama", "input_tokens": 80, "output_tokens": 40,
                "total_tokens": 120, "cost_usd": 0.00008, "latency_s": 0.4,
                "prompt_version": prompt_version,
            }
        raise AssertionError(f"unexpected schema: {schema}")


class _FakeClientFailure:
    is_available = True

    def complete_structured(self, **kw):
        raise LLMError("simulated LLM failure")


class _FakeClientUnavailable:
    is_available = False

    def complete_structured(self, **kw):
        raise LLMError("no api key")


# ---------- Graph integration tests ----------

def test_llm_reasoner_uses_llm_output(seeded_memory_leak, monkeypatch):
    rc = LLMRootCause(
        category="memory",
        primary_service="order-service",
        primary_metric="memory_mb",
        hypothesis="Memory leak on order-service — 4x growth over 4 minutes",
        confidence="high",
        severity=3,
        evidence_summary=["322 -> 1459 MB", "4.5x growth", "no error spans"],
        candidates=[LLMCandidate(
            service="order-service", metric="memory_mb", severity=3,
            baseline_ratio=2.8, reason="steady growth pattern",
        )],
    )
    rem = LLMRemediation(
        action="restart_service",
        target_service="order-service",
        reason="Rolling restart releases leaked memory",
        risk_level="medium",
        requires_approval=True,
        steps=[LLMRemediationStep(
            order=1,
            action="rolling_restart",
            command="kubectl rollout restart deployment/order-service -n production",
            reason="Release leaked memory",
            risk="medium",
        )],
        estimated_mttr_minutes=5,
    )
    fake = _FakeClientSuccess(rc, rem)
    monkeypatch.setattr(rlm, "_client", fake)
    monkeypatch.setattr(remlm, "_client", fake)

    graph = build_graph()
    result = graph.invoke({
        "incident_id": "inc_x",
        "run_id": "run_leak",
        "scenario": "memory_leak",
        "timeline": [],
    })

    assert result["root_cause"]["category"] == "memory"
    assert result["root_cause"]["primary_service"] == "order-service"
    assert result["root_cause"]["llm_meta"]["used"] is True
    assert result["root_cause"]["llm_meta"]["model"] == "mock-llama"
    assert result["remediation"]["llm_meta"]["used"] is True
    assert result["remediation"]["estimated_mttr_minutes"] == 5
    assert result["remediation"]["steps"][0]["command"].startswith("kubectl")


def test_llm_reasoner_falls_back_on_failure(seeded_memory_leak, monkeypatch):
    monkeypatch.setattr(rlm, "_client", _FakeClientFailure())
    monkeypatch.setattr(remlm, "_client", _FakeClientFailure())

    graph = build_graph()
    result = graph.invoke({
        "incident_id": "inc_x",
        "run_id": "run_leak",
        "scenario": "memory_leak",
        "timeline": [],
    })

    assert result["root_cause"]["category"] == "memory"
    assert result["root_cause"]["primary_service"] == "order-service"
    assert result["root_cause"]["llm_meta"]["used"] is False
    assert "fallback_reason" in result["root_cause"]["llm_meta"]
    assert result["remediation"]["action"] == "restart_service"


def test_llm_reasoner_disabled_no_key(seeded_memory_leak, monkeypatch):
    monkeypatch.setattr(rlm, "_client", _FakeClientUnavailable())
    monkeypatch.setattr(remlm, "_client", _FakeClientUnavailable())

    graph = build_graph()
    result = graph.invoke({
        "incident_id": "inc_x",
        "run_id": "run_leak",
        "scenario": "memory_leak",
        "timeline": [],
    })

    assert result["root_cause"]["category"] == "memory"
    assert result["root_cause"]["llm_meta"]["used"] is False


def test_llm_healthy_path(seeded_memory_leak, monkeypatch):
    rc = LLMRootCause(
        category="healthy",
        primary_service=None,
        primary_metric=None,
        hypothesis="All metrics within normal bounds",
        confidence="high",
        severity=0,
        evidence_summary=["all severities 0"],
    )
    rem = LLMRemediation(
        action="no_action",
        target_service=None,
        reason="Healthy — no action",
        risk_level="none",
        requires_approval=False,
        steps=[],
        estimated_mttr_minutes=0,
    )
    fake = _FakeClientSuccess(rc, rem)
    monkeypatch.setattr(rlm, "_client", fake)
    monkeypatch.setattr(remlm, "_client", fake)

    graph = build_graph()
    result = graph.invoke({
        "incident_id": "inc_x",
        "run_id": "run_leak",
        "scenario": "memory_leak",
        "timeline": [],
    })

    assert result["root_cause"]["category"] == "healthy"
    assert result["root_cause"]["primary_service"] is None
    assert result["remediation"]["action"] == "no_action"
    assert result["remediation"]["requires_approval"] is False
    assert result["root_cause"]["llm_meta"]["used"] is True


# ---------- Lenient schema tests ----------

def test_llm_schema_normalizes_invalid_category():
    rc = LLMRootCause(
        category="not-a-category",  # type: ignore[arg-type]
        hypothesis="x",
        confidence="high",
        severity=0,
    )
    assert rc.category == "unknown"


def test_llm_schema_clamps_severity_out_of_range():
    rc_high = LLMRootCause(
        category="memory", hypothesis="x", confidence="high", severity=99,
    )
    assert rc_high.severity == 3

    rc_low = LLMRootCause(
        category="memory", hypothesis="x", confidence="high", severity=-5,
    )
    assert rc_low.severity == 0


def test_llm_schema_normalizes_category_aliases():
    assert LLMRootCause(
        category="memory_leak", hypothesis="x", confidence="HIGH", severity=3,
    ).category == "memory"

    assert LLMRootCause(
        category="db", hypothesis="x", confidence="medium", severity=2,
    ).category == "latency"

    assert LLMRootCause(
        category="CPU-SPIKE", hypothesis="x", confidence="low", severity=3,
    ).category == "cpu"

    rc = LLMRootCause(category="memory", hypothesis="x", confidence="HIGH", severity=3)
    assert rc.confidence == "high"


def test_llm_schema_normalizes_action_aliases():
    rem = LLMRemediation(
        action="restart",  # type: ignore[arg-type]
        target_service="order-service",
        reason="x",
        risk_level="MEDIUM",  # type: ignore[arg-type]
        requires_approval="true",  # type: ignore[arg-type]
        steps=[],
        estimated_mttr_minutes=5,
    )
    assert rem.action == "restart_service"
    assert rem.risk_level == "medium"
    assert rem.requires_approval is True

    rem2 = LLMRemediation(
        action="rollback",  # type: ignore[arg-type]
        target_service="auth-service",
        reason="x",
        risk_level="high",
        requires_approval=True,
        steps=[],
        estimated_mttr_minutes=10,
    )
    assert rem2.action == "rollback_deployment"


def test_llm_schema_mttr_alias():
    rem = LLMRemediation.model_validate({
        "action": "restart_service",
        "target_service": "order-service",
        "reason": "x",
        "risk_level": "medium",
        "requires_approval": True,
        "steps": [],
        "mttr_minutes": 7,  # alias!
    })
    assert rem.estimated_mttr_minutes == 7