"""Tests for the anomaly detection pipeline."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.anomaly import AnomalyDetector
from app.ml.baseline import BaselineStats
from app.ml.features import FEATURE_COLUMNS, compute_series_features


def _make_series(values: list[float], start="2026-01-01T00:00:00") -> pd.DataFrame:
    ts = pd.date_range(start=start, periods=len(values), freq="s")
    return pd.DataFrame({"timestamp": ts, "value": values})


def test_baseline_fit_and_zscore():
    baseline = BaselineStats().fit([
        ("svc-a", "cpu_percent", 40.0),
        ("svc-a", "cpu_percent", 42.0),
        ("svc-a", "cpu_percent", 38.0),
        ("svc-a", "cpu_percent", 41.0),
    ])
    b = baseline.get("svc-a", "cpu_percent")
    assert b is not None
    assert abs(b.mean - 40.25) < 0.5
    assert b.count == 4
    assert baseline.get("missing", "metric") is None


def test_feature_computation_returns_expected_columns():
    baseline = BaselineStats().fit(
        [("svc", "cpu_percent", v) for v in [40, 41, 39, 40, 42]]
    )
    series = _make_series([40, 41, 40, 42, 41])
    feats = compute_series_features(
        series, baseline, service="svc", metric="cpu_percent"
    )
    for col in FEATURE_COLUMNS:
        assert col in feats.columns
    assert len(feats) == 5
    assert feats["value"].tolist() == [40, 41, 40, 42, 41]


def test_detector_fit_and_predict():
    baseline = BaselineStats().fit(
        [("svc", "cpu_percent", v) for v in [40, 41, 39, 40, 42, 41, 40]]
    )
    normal_series = _make_series([40, 41, 39, 40, 42, 41, 40, 41, 40, 39])
    X = compute_series_features(
        normal_series, baseline, service="svc", metric="cpu_percent"
    )

    det = AnomalyDetector(n_estimators=50, contamination=0.1, random_state=7)
    det.fit(X, baseline)
    assert det.is_fitted

    preds = det.predict(X)
    assert set(np.unique(preds)).issubset({-1, 1})
    scores = det.score(X)
    assert len(scores) == len(X)


def test_detector_flags_high_value_as_anomaly():
    baseline = BaselineStats().fit(
        [("svc", "cpu_percent", v) for v in [40, 41, 39, 40, 42, 41, 40, 39, 40, 41]]
    )
    normal_series = _make_series([40, 41, 39, 40, 42, 41, 40, 41, 40, 39])
    X_normal = compute_series_features(
        normal_series, baseline, service="svc", metric="cpu_percent"
    )

    det = AnomalyDetector(n_estimators=80, contamination=0.1, random_state=7)
    det.fit(X_normal, baseline)

    spike_series = _make_series([40, 41, 39, 40, 42, 41, 40, 41, 40, 200])
    X_spike = compute_series_features(
        spike_series, baseline, service="svc", metric="cpu_percent"
    )
    preds = det.predict(X_spike)
    assert preds[-1] == -1


def test_detector_save_load(tmp_path):
    baseline = BaselineStats().fit(
        [("svc", "cpu_percent", v) for v in [40, 41, 39, 40, 42]]
    )
    series = _make_series([40, 41, 39, 40, 42])
    X = compute_series_features(
        series, baseline, service="svc", metric="cpu_percent"
    )
    det = AnomalyDetector(n_estimators=30, contamination=0.1, random_state=7)
    det.fit(X, baseline)
    det.save(tmp_path)

    loaded = AnomalyDetector.load(tmp_path)
    assert loaded.is_fitted
    assert loaded.contamination == 0.1
    assert loaded.n_estimators == 30
    assert len(loaded.baseline) == 1