"""Runs a simulation over time and writes telemetry to disk."""
from __future__ import annotations

import time
from datetime import datetime

from app.config import get_settings
from app.logging_config import get_logger
from sim.config import SERVICE_NAMES
from sim.generator import TelemetryGenerator
from sim.models import (
    IncidentScenario,
    SimulationMetadata,
    new_id,
    utc_now,
)

logger = get_logger("sim.runner")


class SimulationRunner:
    """Simulates infrastructure and writes telemetry JSONL files."""

    def __init__(
        self,
        scenario: IncidentScenario = IncidentScenario.NORMAL,
        duration_seconds: float = 60.0,
        tick_interval_seconds: float = 1.0,
        seed: int | None = None,
        run_id: str | None = None,
        speedup: float = 1.0,
    ):
        self.scenario = scenario
        self.duration_seconds = duration_seconds
        self.tick_interval_seconds = tick_interval_seconds
        self.seed = seed
        self.run_id = run_id or f"run_{new_id()[:12]}"
        self.speedup = max(1.0, speedup)
        self._settings = get_settings()
        self._generator = TelemetryGenerator(scenario, seed=seed)
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> SimulationMetadata:
        settings = self._settings
        base = settings.data_dir
        metrics_path = base / "metrics" / f"{self.run_id}.jsonl"
        logs_path = base / "logs" / f"{self.run_id}.jsonl"
        traces_path = base / "traces" / f"{self.run_id}.jsonl"
        meta_path = base / "runs" / f"{self.run_id}.json"

        for p in (metrics_path, logs_path, traces_path, meta_path):
            p.parent.mkdir(parents=True, exist_ok=True)

        started = utc_now()
        logger.info(
            "simulation_started",
            run_id=self.run_id,
            scenario=self.scenario.value,
            duration_seconds=self.duration_seconds,
            tick_interval_seconds=self.tick_interval_seconds,
        )

        total_ticks = max(1, int(self.duration_seconds / self.tick_interval_seconds))
        m_count = l_count = s_count = 0

        with (
            metrics_path.open("w", encoding="utf-8") as mf,
            logs_path.open("w", encoding="utf-8") as lf,
            traces_path.open("w", encoding="utf-8") as tf,
        ):
            start_wall = time.monotonic()
            for i in range(total_ticks):
                if self._stop_requested:
                    logger.info("simulation_stopped", run_id=self.run_id, tick=i)
                    break

                progress = i / total_ticks
                ts = utc_now()
                metrics, logs, spans = self._generator.tick(ts, progress)

                for m in metrics:
                    mf.write(m.model_dump_json() + "\n")
                for lg in logs:
                    lf.write(lg.model_dump_json() + "\n")
                for s in spans:
                    tf.write(s.model_dump_json() + "\n")

                m_count += len(metrics)
                l_count += len(logs)
                s_count += len(spans)

                target = start_wall + (i + 1) * self.tick_interval_seconds / self.speedup
                sleep_for = target - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)

        ended = utc_now()
        meta = SimulationMetadata(
            run_id=self.run_id,
            scenario=self.scenario,
            started_at=started,
            ended_at=ended,
            duration_seconds=(ended - started).total_seconds(),
            tick_interval_seconds=self.tick_interval_seconds,
            metrics_count=m_count,
            logs_count=l_count,
            spans_count=s_count,
            services=SERVICE_NAMES,
            config={
                "seed": self.seed,
                "speedup": self.speedup,
                "target_duration_seconds": self.duration_seconds,
            },
        )
        meta_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        logger.info(
            "simulation_finished",
            run_id=self.run_id,
            metrics=m_count,
            logs=l_count,
            spans=s_count,
            duration_s=round(meta.duration_seconds, 2),
        )
        return meta