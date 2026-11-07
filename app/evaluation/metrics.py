"""Metrics calculation for evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScenarioResult:
    run_id: str
    scenario: str

    # Predictions
    predicted_category: str
    predicted_service: str | None
    predicted_metric: str | None

    # Ground truth
    expected_category: str
    expected_service: str | None
    expected_metric: str | None
    expected_runbook: str | None

    # Scores
    category_correct: bool
    service_correct: bool
    metric_correct: bool
    overall_correct: bool  # category AND service (for anomalies)

    # RAG
    retrieved_runbook_ids: list[str] = field(default_factory=list)
    runbook_retrieved: bool = False

    # Cost / latency
    llm_used: bool = False
    cost_usd: float = 0.0
    latency_s: float = 0.0


@dataclass
class EvaluationReport:
    total_scenarios: int
    results: list[ScenarioResult]

    @property
    def category_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.category_correct) / len(self.results)

    @property
    def service_accuracy(self) -> float:
        # Only evaluate service for anomaly scenarios (healthy has no service)
        anomaly = [r for r in self.results if r.expected_category != "healthy"]
        if not anomaly:
            return 0.0
        return sum(1 for r in anomaly if r.service_correct) / len(anomaly)

    @property
    def metric_accuracy(self) -> float:
        anomaly = [r for r in self.results if r.expected_metric is not None]
        if not anomaly:
            return 0.0
        return sum(1 for r in anomaly if r.metric_correct) / len(anomaly)

    @property
    def overall_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.overall_correct) / len(self.results)

    @property
    def rag_precision(self) -> float:
        # Only for runs where we expected a specific runbook
        expected = [r for r in self.results if r.expected_runbook]
        if not expected:
            return 0.0
        return sum(1 for r in expected if r.runbook_retrieved) / len(expected)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.results), 6)

    @property
    def avg_latency_s(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(r.latency_s for r in self.results) / len(self.results), 2)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_scenarios": self.total_scenarios,
                "category_accuracy": round(self.category_accuracy, 4),
                "service_accuracy": round(self.service_accuracy, 4),
                "metric_accuracy": round(self.metric_accuracy, 4),
                "overall_accuracy": round(self.overall_accuracy, 4),
                "rag_precision": round(self.rag_precision, 4),
                "total_cost_usd": self.total_cost_usd,
                "avg_latency_s": self.avg_latency_s,
            },
            "results": [
                {
                    "run_id": r.run_id,
                    "scenario": r.scenario,
                    "predicted": {
                        "category": r.predicted_category,
                        "service": r.predicted_service,
                        "metric": r.predicted_metric,
                    },
                    "expected": {
                        "category": r.expected_category,
                        "service": r.expected_service,
                        "metric": r.expected_metric,
                        "runbook": r.expected_runbook,
                    },
                    "scores": {
                        "category_correct": r.category_correct,
                        "service_correct": r.service_correct,
                        "metric_correct": r.metric_correct,
                        "overall_correct": r.overall_correct,
                        "runbook_retrieved": r.runbook_retrieved,
                    },
                    "llm": {
                        "used": r.llm_used,
                        "cost_usd": round(r.cost_usd, 6),
                        "latency_s": round(r.latency_s, 2),
                    },
                }
                for r in self.results
            ],
        }