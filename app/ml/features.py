"""Feature engineering for anomaly detection."""
from __future__ import annotations

import pandas as pd

from app.ml.baseline import BaselineStats

FEATURE_COLUMNS = [
    "value_ratio",
    "zscore",
    "rolling_mean_ratio",
    "rolling_std_ratio",
    "delta_zscore",
]


def compute_series_features(
    series_df: pd.DataFrame,
    baseline: BaselineStats,
    service: str,
    metric: str,
    window: int = 5,
) -> pd.DataFrame:
    df = series_df.sort_values("timestamp").reset_index(drop=True).copy()
    values = df["value"].astype(float)

    b = baseline.get_or_default(service, metric)
    eps = 1e-6
    safe_mean = b.mean if abs(b.mean) > eps else eps
    safe_std = b.std if abs(b.std) > eps else eps

    out = pd.DataFrame(index=df.index)
    out["timestamp"] = df["timestamp"]
    out["value"] = values
    out["value_ratio"] = values / safe_mean
    out["zscore"] = (values - b.mean) / safe_std
    rolling_mean = values.rolling(window, min_periods=1).mean()
    out["rolling_mean_ratio"] = rolling_mean / safe_mean
    rolling_std = values.rolling(window, min_periods=1).std().fillna(0.0)
    out["rolling_std_ratio"] = rolling_std / safe_std
    delta = values.diff().fillna(0.0)
    out["delta_zscore"] = delta / safe_std

    return out