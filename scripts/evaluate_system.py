"""Run full evaluation from CLI and print results."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.runner import run_evaluation
from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("scripts.evaluate")


def main() -> None:
    print("=" * 70)
    print(" AegisOps — AI Evaluation")
    print("=" * 70)

    report = run_evaluation()
    d = report.to_dict()

    print()
    print(f" {'scenario':<18} {'pred_cat':<12} {'exp_cat':<12} {'cat':>4} {'svc':>4} {'ovr':>4} {'rag':>4} {'cost':>8}")
    print("-" * 80)
    for r in d["results"]:
        s = r["scores"]
        llm = r["llm"]
        print(
            f" {r['scenario']:<18} "
            f"{r['predicted']['category']:<12} "
            f"{r['expected']['category']:<12} "
            f"{'✅' if s['category_correct'] else '❌':>4} "
            f"{'✅' if s['service_correct'] else '❌':>4} "
            f"{'✅' if s['overall_correct'] else '❌':>4} "
            f"{'✅' if s['runbook_retrieved'] else '❌':>4} "
            f"${llm['cost_usd']:>7.5f}"
        )

    print("-" * 80)
    summ = d["summary"]
    print()
    print(f"  Total scenarios     : {summ['total_scenarios']}")
    print(f"  Category accuracy   : {summ['category_accuracy']:.2%}")
    print(f"  Service accuracy    : {summ['service_accuracy']:.2%}")
    print(f"  Metric accuracy     : {summ['metric_accuracy']:.2%}")
    print(f"  Overall accuracy    : {summ['overall_accuracy']:.2%}")
    print(f"  RAG precision       : {summ['rag_precision']:.2%}")
    print(f"  Total cost (USD)    : ${summ['total_cost_usd']:.5f}")
    print(f"  Avg latency (s)     : {summ['avg_latency_s']:.2f}")

    out_path = Path("data/evaluation_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print()
    print(f"  Report saved to     : {out_path}")


if __name__ == "__main__":
    main()