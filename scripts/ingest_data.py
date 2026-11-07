"""Ingest simulated telemetry JSONL files into SQLite."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.logging_config import configure_logging, get_logger
from app.pipeline.ingestor import TelemetryIngestor
from app.storage.database import get_session_factory, init_db

configure_logging()
logger = get_logger("scripts.ingest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest AegisOps telemetry into SQLite")
    parser.add_argument("--run-id", help="Ingest only this run_id")
    parser.add_argument("--list", action="store_true", help="List available runs on disk")
    args = parser.parse_args()

    init_db()
    ingestor = TelemetryIngestor()

    if args.list:
        runs = ingestor.available_runs()
        print(f"\nAvailable runs on disk ({len(runs)}):")
        for r in runs:
            print(f"  {r}")
        return

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        if args.run_id:
            result = ingestor.ingest_run(args.run_id, session)
            if result is None:
                print(f"[skip] {args.run_id} already ingested or no data")
            else:
                print(f"[ok]   {result}")
        else:
            results = ingestor.ingest_all(session)
            if not results:
                print("Nothing new to ingest.")
            for r in results:
                print(f"[ok]   {r}")
            print(f"\nTotal: {len(results)} runs ingested")


if __name__ == "__main__":
    main()