"""Isolation Forest-based anomaly detector."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.ml.baseline import BaselineStats
from app.ml.features import FEATURE_COLUMNS


@dataclass
class DetectionResult:
    timestamp: str
    service: str
    metric_name: str
    value: float
    anomaly_score: float
    is_anomaly: bool


@dataclass
class DetectionSummary:
    run_id: str
    total_points: int
    anomaly_count: int
    anomaly_rate: float
    by_service: dict[str, int] = field(default_factory=dict)
    by_metric: dict[str, int] = field(default_factory=dict)
    top_anomalies: list[dict] = field(default_factory=list)


class AnomalyDetector:
    """Wrapper around sklearn IsolationForest with baseline-aware features."""

    def __init__(
        self,
        n_estimators: int = 150,
        contamination: float = 0.05,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.baseline: BaselineStats | None = None
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, X: pd.DataFrame, baseline: BaselineStats) -> "AnomalyDetector":
        if X.empty:
            raise ValueError("Cannot fit on empty features")
        self.baseline = baseline
        X_values = X[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
        X_scaled = self.scaler.fit_transform(X_values)
        self.model.fit(X_scaled)
        self._fitted = True
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        X_values = X[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
        X_scaled = self.scaler.transform(X_values)
        return -self.model.score_samples(X_scaled)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        X_values = X[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
        X_scaled = self.scaler.transform(X_values)
        return self.model.predict(X_scaled)

    def save(self, model_dir: Path) -> None:
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "random_state": self.random_state,
        }, model_dir / "anomaly_detector.pkl")

        if self.baseline is not None:
            self.baseline.save(model_dir / "baseline.json")

        meta = {
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "random_state": self.random_state,
            "feature_columns": FEATURE_COLUMNS,
            "baseline_series_count": len(self.baseline) if self.baseline else 0,
        }
        (model_dir / "model_meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, model_dir: Path) -> "AnomalyDetector":
        payload = joblib.load(model_dir / "anomaly_detector.pkl")
        det = cls(
            n_estimators=payload["n_estimators"],
            contamination=payload["contamination"],
            random_state=payload["random_state"],
        )
        det.model = payload["model"]
        det.scaler = payload["scaler"]
        det.baseline = BaselineStats.load(model_dir / "baseline.json")
        det._fitted = True
        return det