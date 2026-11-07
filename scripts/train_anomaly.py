"""Train the anomaly detector on NORMAL scenario data."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mlflow
import mlflow.sklearn  # noqa: F401

from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.baseline import BaselineStats
from app.ml.features import compute_series_features
from app.storage.database import get_session_factory, init_db
from app.storage.models import IngestionRun, MetricRow

configure_logging()
logger = get_logger("scripts.train_anomaly")

WINDOW = 5
N_ESTIMATORS = 150
CONTAMINATION = 0.05


def load_normal_metrics(session) -> pd.DataFrame:
    normal_runs = [
        r.run_id for r in session.query(IngestionRun).filter_by(scenario="normal").all()
    ]
    if not normal_runs:
        raise RuntimeError("No NORMAL scenario runs found. Run simulator first.")
    logger.info("loading_normal_runs", count=len(normal_runs), runs=normal_runs)

    rows = session.query(
        MetricRow.timestamp, MetricRow.service, MetricRow.metric_name, MetricRow.value
    ).filter(MetricRow.run_id.in_(normal_runs)).all()

    df = pd.DataFrame(rows, columns=["timestamp", "service", "metric_name", "value"])
    logger.info("loaded_normal_metrics", rows=len(df))
    return df


def build_training_features(df: pd.DataFrame) -> tuple[pd.DataFrame, BaselineStats]:
    baseline = BaselineStats().fit(
        zip(df["service"], df["metric_name"], df["value"])
    )
    logger.info("baseline_fitted", series=len(baseline))

    feature_frames: list[pd.DataFrame] = []
    for (service, metric), group in df.groupby(["service", "metric_name"]):
        feats = compute_series_features(
            group[["timestamp", "value"]],
            baseline,
            service=service,
            metric=metric,
            window=WINDOW,
        )
        feats["service"] = service
        feats["metric_name"] = metric
        feature_frames.append(feats)

    X = pd.concat(feature_frames, ignore_index=True)
    logger.info("features_built", rows=len(X))
    return X, baseline


def main() -> None:
    settings = get_settings()
    init_db()
    model_dir = settings.models_dir

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        df = load_normal_metrics(session)

    X, baseline = build_training_features(df)
    detector = AnomalyDetector(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
    )
    detector.fit(X, baseline)

    scores = detector.score(X)
    preds = detector.predict(X)
    anomaly_rate = float((preds == -1).mean())
    logger.info(
        "training_complete",
        total=len(X),
        anomaly_rate=round(anomaly_rate, 4),
        score_mean=round(float(scores.mean()), 4),
        score_std=round(float(scores.std()), 4),
    )

    detector.save(model_dir)
    logger.info("model_saved", path=str(model_dir))

    if settings.mlflow_enabled:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
        with mlflow.start_run(run_name="isolation_forest_v1"):
            mlflow.log_params({
                "model": "IsolationForest",
                "n_estimators": N_ESTIMATORS,
                "contamination": CONTAMINATION,
                "random_state": 42,
                "window": WINDOW,
                "n_features": len(X.columns),
                "n_normal_rows": len(X),
                "baseline_series": len(baseline),
            })
            mlflow.log_metrics({
                "train_anomaly_rate": anomaly_rate,
                "train_score_mean": float(scores.mean()),
                "train_score_std": float(scores.std()),
                "train_score_p95": float(pd.Series(scores).quantile(0.95)),
                "train_score_max": float(scores.max()),
            })
            mlflow.log_artifact(str(model_dir / "baseline.json"))
            mlflow.log_artifact(str(model_dir / "model_meta.json"))
            mlflow.log_artifact(str(model_dir / "anomaly_detector.pkl"))
        logger.info("mlflow_logged", experiment=settings.mlflow_experiment_name)

    print()
    print("=" * 55)
    print(" Training complete")
    print("=" * 55)
    print(f"  Baseline series    : {len(baseline)}")
    print(f"  Training rows      : {len(X)}")
    print(f"  Train anomaly rate : {anomaly_rate:.2%}  (contamination={CONTAMINATION})")
    print(f"  Score mean / std   : {scores.mean():.4f} / {scores.std():.4f}")
    print(f"  Model dir          : {model_dir}")
    print(f"  MLflow experiment  : {settings.mlflow_experiment_name}")


if __name__ == "__main__":
    main()