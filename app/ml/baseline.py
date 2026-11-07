"""Per-(service, metric) baseline statistics from NORMAL runs."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass
class SeriesBaseline:
    mean: float
    std: float
    median: float
    p95: float
    p99: float
    min: float
    max: float
    count: int


@dataclass
class BaselineStats:
    """Baseline for all (service, metric) pairs."""
    series: dict[str, SeriesBaseline] = field(default_factory=dict)

    @staticmethod
    def _key(service: str, metric: str) -> str:
        return f"{service}::{metric}"

    def fit(self, rows: Iterable[tuple[str, str, float]]) -> "BaselineStats":
        grouped: dict[str, list[float]] = {}
        for service, metric, value in rows:
            grouped.setdefault(self._key(service, metric), []).append(value)

        for key, values in grouped.items():
            arr = np.asarray(values, dtype=np.float64)
            self.series[key] = SeriesBaseline(
                mean=float(np.mean(arr)),
                std=float(np.std(arr)) or 1e-6,
                median=float(np.median(arr)),
                p95=float(np.percentile(arr, 95)),
                p99=float(np.percentile(arr, 99)),
                min=float(np.min(arr)),
                max=float(np.max(arr)),
                count=len(arr),
            )
        return self

    def get(self, service: str, metric: str) -> SeriesBaseline | None:
        return self.series.get(self._key(service, metric))

    def get_or_default(self, service: str, metric: str) -> SeriesBaseline:
        b = self.get(service, metric)
        if b is not None:
            return b
        return SeriesBaseline(
            mean=1.0, std=1.0, median=1.0, p95=1.0, p99=1.0,
            min=0.0, max=1.0, count=0,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            k: {
                "mean": v.mean, "std": v.std, "median": v.median,
                "p95": v.p95, "p99": v.p99, "min": v.min, "max": v.max,
                "count": v.count,
            }
            for k, v in self.series.items()
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BaselineStats":
        payload = json.loads(path.read_text(encoding="utf-8"))
        stats = cls()
        for k, v in payload.items():
            stats.series[k] = SeriesBaseline(**v)
        return stats

    def __len__(self) -> int:
        return len(self.series)