"""Evaluate the trained anomaly detector on anomaly scenarios."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.features import compute_series_features
from app.storage.database import get_session_factory
from app.storage.models import IngestionRun, MetricRow

configure_logging()
logger = get_logger("scripts.evaluate_anomaly")

WINDOW = 5


def load_run_metrics(session, run_id: str) -> pd.DataFrame:
    rows = session.query(
        MetricRow.timestamp, MetricRow.service, MetricRow.metric_name, MetricRow.value
    ).filter(MetricRow.run_id == run_id).all()
    return pd.DataFrame(rows, columns=["timestamp", "service", "metric_name", "value"])


def score_run(detector: AnomalyDetector, df: pd.DataFrame) -> tuple[int, int]:
    if df.empty:
        return 0, 0
    total = 0
    anomalies = 0
    for (service, metric), group in df.groupby(["service", "metric_name"]):
        feats = compute_series_features(
            group[["timestamp", "value"]],
            detector.baseline,
            service=service,
            metric=metric,
            window=WINDOW,
        )
        preds = detector.predict(feats)
        total += len(preds)
        anomalies += int((preds == -1).sum())
    return total, anomalies


def main() -> None:
    settings = get_settings()
    model_dir = settings.models_dir
    if not (model_dir / "anomaly_detector.pkl").exists():
        print(f"[error] No model at {model_dir}. Run scripts/train_anomaly.py first.")
        return

    detector = AnomalyDetector.load(model_dir)
    logger.info("model_loaded", baseline_series=len(detector.baseline))

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        runs = session.query(IngestionRun).all()

        print()
        print("=" * 70)
        print(f" {'scenario':<18} {'run_id':<22} {'total':>6} {'anom':>6} {'rate':>8}")
        print("=" * 70)

        fpr_total = 0
        fpr_anom = 0
        for r in runs:
            df = load_run_metrics(session, r.run_id)
            total, anomalies = score_run(detector, df)
            rate = (anomalies / total) if total else 0.0
            marker = ""
            if r.scenario == "normal":
                fpr_total = total
                fpr_anom = anomalies
                marker = "  <- FPR target <5%"
            print(
                f" {r.scenario:<18} {r.run_id:<22} {total:>6} {anomalies:>6} "
                f"{rate:>7.2%}{marker}"
            )

        print("=" * 70)
        if fpr_total:
            fpr = fpr_anom / fpr_total
            status = "PASS" if fpr < 0.055 else "REVIEW"
            print(f" False positive rate on NORMAL: {fpr:.2%}  [{status}]")
        print()


if __name__ == "__main__":
    main()