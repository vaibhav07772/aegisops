"""Ingests simulated telemetry JSONL files into SQLite."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_config import get_logger
from app.storage import repositories as repo

logger = get_logger("pipeline.ingestor")


def _parse_ts(raw: str) -> datetime:
    """Parse ISO8601 -> naive UTC datetime (SQLite stores naive)."""
    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


class TelemetryIngestor:
    """Reads simulation JSONL files and writes them into SQLite."""

    def __init__(self, data_dir: Path | None = None):
        settings = get_settings()
        self.data_dir = data_dir or settings.data_dir
        self.metrics_dir = self.data_dir / "metrics"
        self.logs_dir = self.data_dir / "logs"
        self.traces_dir = self.data_dir / "traces"
        self.runs_dir = self.data_dir / "runs"

    def available_runs(self) -> list[str]:
        """Return run_ids that exist on disk (from metrics/*.jsonl)."""
        if not self.metrics_dir.exists():
            return []
        return sorted(p.stem for p in self.metrics_dir.glob("*.jsonl"))

    def _load_meta(self, run_id: str) -> dict:
        meta_path = self.runs_dir / f"{run_id}.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding="utf-8"))
        return {}

    def ingest_run(self, run_id: str, session: Session) -> dict | None:
        """Ingest a single run. Returns counts, or None if skipped."""
        if repo.is_run_ingested(session, run_id):
            logger.info("ingestion_skipped_already_present", run_id=run_id)
            return None

        meta = self._load_meta(run_id)
        scenario = meta.get("scenario", "unknown")

        metric_rows: list[dict] = []
        for m in _read_jsonl(self.metrics_dir / f"{run_id}.jsonl"):
            metric_rows.append({
                "run_id": run_id,
                "timestamp": _parse_ts(m["timestamp"]),
                "service": m["service"],
                "metric_name": m["metric_name"],
                "value": float(m["value"]),
            })

        log_rows: list[dict] = []
        for lg in _read_jsonl(self.logs_dir / f"{run_id}.jsonl"):
            log_rows.append({
                "run_id": run_id,
                "timestamp": _parse_ts(lg["timestamp"]),
                "service": lg["service"],
                "level": lg["level"],
                "message": lg["message"],
                "trace_id": lg.get("trace_id"),
                "span_id": lg.get("span_id"),
            })

        span_rows: list[dict] = []
        for s in _read_jsonl(self.traces_dir / f"{run_id}.jsonl"):
            span_rows.append({
                "run_id": run_id,
                "timestamp": _parse_ts(s["timestamp"]),
                "trace_id": s["trace_id"],
                "span_id": s["span_id"],
                "parent_span_id": s.get("parent_span_id"),
                "service": s["service"],
                "operation": s["operation"],
                "duration_ms": float(s["duration_ms"]),
                "status": s.get("status", "ok"),
            })

        if not metric_rows and not log_rows and not span_rows:
            logger.warning("ingestion_no_data", run_id=run_id)
            return None

        try:
            repo.bulk_insert_metrics(session, metric_rows)
            repo.bulk_insert_logs(session, log_rows)
            repo.bulk_insert_spans(session, span_rows)

            repo.record_ingestion(
                session,
                run_id=run_id,
                scenario=scenario,
                ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
                metrics_count=len(metric_rows),
                logs_count=len(log_rows),
                spans_count=len(span_rows),
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("ingestion_failed", run_id=run_id)
            raise

        result = {
            "run_id": run_id,
            "scenario": scenario,
            "metrics": len(metric_rows),
            "logs": len(log_rows),
            "spans": len(span_rows),
        }
        logger.info("ingestion_completed", **result)
        return result

    def ingest_all(self, session: Session) -> list[dict]:
        results: list[dict] = []
        for run_id in self.available_runs():
            result = self.ingest_run(run_id, session)
            if result:
                results.append(result)
        return results