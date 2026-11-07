"""Tests for evaluation metrics (no LLM calls — pure logic)."""
from __future__ import annotations

from app.evaluation.ground_truth import GROUND_TRUTH
from app.evaluation.metrics import EvaluationReport, ScenarioResult


def _make_result(
    *,
    scenario: str,
    pred_cat: str,
    pred_svc: str | None,
    pred_metric: str | None,
    exp_cat: str,
    exp_svc: str | None,
    exp_metric: str | None,
    exp_runbook: str | None,
    retrieved: list[str] | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        run_id=f"run_{scenario}",
        scenario=scenario,
        predicted_category=pred_cat,
        predicted_service=pred_svc,
        predicted_metric=pred_metric,
        expected_category=exp_cat,
        expected_service=exp_svc,
        expected_metric=exp_metric,
        expected_runbook=exp_runbook,
        category_correct=pred_cat == exp_cat,
        service_correct=pred_svc == exp_svc,
        metric_correct=pred_metric == exp_metric,
        overall_correct=(pred_cat == exp_cat and (pred_svc == exp_svc if exp_svc else True)),
        retrieved_runbook_ids=retrieved or [],
        runbook_retrieved=(exp_runbook in (retrieved or [])) if exp_runbook else True,
    )


def test_ground_truth_has_all_6_scenarios():
    expected = {"normal", "memory_leak", "slow_database",
                "service_outage", "cpu_spike", "error_cascade"}
    assert set(GROUND_TRUTH.keys()) == expected


def test_category_accuracy_all_correct():
    results = [
        _make_result(
            scenario="memory_leak", pred_cat="memory", pred_svc="order-service",
            pred_metric="memory_mb", exp_cat="memory", exp_svc="order-service",
            exp_metric="memory_mb", exp_runbook="memory_leak",
            retrieved=["memory_leak"],
        ),
        _make_result(
            scenario="cpu_spike", pred_cat="cpu", pred_svc="api-gateway",
            pred_metric="cpu_percent", exp_cat="cpu", exp_svc="api-gateway",
            exp_metric="cpu_percent", exp_runbook="cpu_spike",
            retrieved=["cpu_spike"],
        ),
    ]
    r = EvaluationReport(total_scenarios=2, results=results)
    assert r.category_accuracy == 1.0
    assert r.service_accuracy == 1.0
    assert r.overall_accuracy == 1.0
    assert r.rag_precision == 1.0


def test_category_accuracy_mixed():
    results = [
        _make_result(
            scenario="memory_leak", pred_cat="memory", pred_svc="order-service",
            pred_metric="memory_mb", exp_cat="memory", exp_svc="order-service",
            exp_metric="memory_mb", exp_runbook="memory_leak",
            retrieved=["memory_leak"],
        ),
        _make_result(
            scenario="cpu_spike", pred_cat="errors", pred_svc="frontend",  # wrong!
            pred_metric="error_rate", exp_cat="cpu", exp_svc="api-gateway",
            exp_metric="cpu_percent", exp_runbook="cpu_spike",
            retrieved=["memory_leak"],  # wrong runbook
        ),
    ]
    r = EvaluationReport(total_scenarios=2, results=results)
    assert r.category_accuracy == 0.5
    assert r.service_accuracy == 0.5
    assert r.overall_accuracy == 0.5
    assert r.rag_precision == 0.5


def test_service_accuracy_excludes_healthy():
    results = [
        _make_result(
            scenario="normal", pred_cat="healthy", pred_svc=None,
            pred_metric=None, exp_cat="healthy", exp_svc=None,
            exp_metric=None, exp_runbook=None, retrieved=[],
        ),
        _make_result(
            scenario="memory_leak", pred_cat="memory", pred_svc="order-service",
            pred_metric="memory_mb", exp_cat="memory", exp_svc="order-service",
            exp_metric="memory_mb", exp_runbook="memory_leak",
            retrieved=["memory_leak"],
        ),
    ]
    r = EvaluationReport(total_scenarios=2, results=results)
    # Only memory_leak counted for service accuracy
    assert r.service_accuracy == 1.0


def test_rag_precision_excludes_no_runbook_scenarios():
    results = [
        _make_result(
            scenario="normal", pred_cat="healthy", pred_svc=None,
            pred_metric=None, exp_cat="healthy", exp_svc=None,
            exp_metric=None, exp_runbook=None, retrieved=[],
        ),
        _make_result(
            scenario="slow_database", pred_cat="latency", pred_svc="postgres-db",
            pred_metric="latency_p95_ms", exp_cat="latency", exp_svc="postgres-db",
            exp_metric="latency_p95_ms", exp_runbook="slow_database",
            retrieved=["slow_database"],
        ),
    ]
    r = EvaluationReport(total_scenarios=2, results=results)
    assert r.rag_precision == 1.0


def test_cost_and_latency_aggregation():
    r1 = _make_result(
        scenario="memory_leak", pred_cat="memory", pred_svc="order-service",
        pred_metric="memory_mb", exp_cat="memory", exp_svc="order-service",
        exp_metric="memory_mb", exp_runbook="memory_leak", retrieved=["memory_leak"],
    )
    r1.cost_usd = 0.001
    r1.latency_s = 4.0

    r2 = _make_result(
        scenario="cpu_spike", pred_cat="cpu", pred_svc="api-gateway",
        pred_metric="cpu_percent", exp_cat="cpu", exp_svc="api-gateway",
        exp_metric="cpu_percent", exp_runbook="cpu_spike", retrieved=["cpu_spike"],
    )
    r2.cost_usd = 0.002
    r2.latency_s = 6.0

    report = EvaluationReport(total_scenarios=2, results=[r1, r2])
    assert report.total_cost_usd == 0.003
    assert report.avg_latency_s == 5.0