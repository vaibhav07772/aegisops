"""Anomaly detection API endpoints."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_config import get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.features import compute_series_features
from app.monitoring import metrics as prom_metrics
from app.storage.database import get_session
from app.storage.models import IngestionRun, MetricRow

logger = get_logger("api.anomaly")
router = APIRouter(prefix="/api/v1/anomaly", tags=["anomaly"])

WINDOW = 5
_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        settings = get_settings()
        model_dir = settings.models_dir
        if not (model_dir / "anomaly_detector.pkl").exists():
            raise HTTPException(
                503,
                f"Model not trained. Run scripts/train_anomaly.py. Expected at {model_dir}",
            )
        _detector = AnomalyDetector.load(model_dir)
        logger.info("detector_loaded", baseline_series=len(_detector.baseline))
    return _detector


class AnomalyPoint(BaseModel):
    timestamp: datetime
    service: str
    metric_name: str
    value: float
    anomaly_score: float
    is_anomaly: bool


class DetectResponse(BaseModel):
    run_id: str
    scenario: str
    total_points: int
    anomaly_count: int
    anomaly_rate: float
    by_service: dict[str, int]
    by_metric: dict[str, int]
    top_anomalies: list[AnomalyPoint]


class HealthResponse(BaseModel):
    status: str
    baseline_series: int
    contamination: float
    n_estimators: int


@router.get("/health", response_model=HealthResponse)
def anomaly_health() -> HealthResponse:
    det = get_detector()
    return HealthResponse(
        status="ready",
        baseline_series=len(det.baseline),
        contamination=det.contamination,
        n_estimators=det.n_estimators,
    )


@router.post("/detect/{run_id}", response_model=DetectResponse)
def detect_run(run_id: str, session: Session = Depends(get_session)) -> DetectResponse:
    run = session.query(IngestionRun).filter_by(run_id=run_id).first()
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")

    rows = session.query(
        MetricRow.timestamp, MetricRow.service, MetricRow.metric_name, MetricRow.value
    ).filter(MetricRow.run_id == run_id).all()
    if not rows:
        raise HTTPException(404, f"No metrics for run '{run_id}'")

    df = pd.DataFrame(rows, columns=["timestamp", "service", "metric_name", "value"])
    detector = get_detector()

    all_points: list[dict] = []
    by_service: dict[str, int] = {}
    by_metric: dict[str, int] = {}

    for (service, metric), group in df.groupby(["service", "metric_name"]):
        feats = compute_series_features(
            group[["timestamp", "value"]],
            detector.baseline,
            service=service,
            metric=metric,
            window=WINDOW,
        )
        scores = detector.score(feats)
        preds = detector.predict(feats)

        for i, row in feats.iterrows():
            is_anomaly = bool(preds[i] == -1)
            point = {
                "timestamp": row["timestamp"].to_pydatetime()
                if hasattr(row["timestamp"], "to_pydatetime")
                else row["timestamp"],
                "service": service,
                "metric_name": metric,
                "value": float(row["value"]),
                "anomaly_score": float(scores[i]),
                "is_anomaly": is_anomaly,
            }
            all_points.append(point)
            if is_anomaly:
                by_service[service] = by_service.get(service, 0) + 1
                by_metric[metric] = by_metric.get(metric, 0) + 1
                prom_metrics.anomalies_detected_total.labels(
                    severity="high" if scores[i] > 0 else "medium"
                ).inc()

    total = len(all_points)
    anomaly_count = sum(1 for p in all_points if p["is_anomaly"])
    top = sorted(
        [p for p in all_points if p["is_anomaly"]],
        key=lambda p: p["anomaly_score"],
        reverse=True,
    )[:20]

    logger.info(
        "detection_completed",
        run_id=run_id,
        scenario=run.scenario,
        total=total,
        anomalies=anomaly_count,
    )

    return DetectResponse(
        run_id=run_id,
        scenario=run.scenario,
        total_points=total,
        anomaly_count=anomaly_count,
        anomaly_rate=anomaly_count / total if total else 0.0,
        by_service=by_service,
        by_metric=by_metric,
        top_anomalies=[AnomalyPoint(**p) for p in top],
    )