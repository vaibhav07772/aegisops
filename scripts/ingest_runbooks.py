"""Ingest runbooks into the vector store."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.logging_config import configure_logging, get_logger
from app.rag.retriever import get_retriever

configure_logging()
logger = get_logger("scripts.ingest_runbooks")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Drop and re-ingest")
    args = parser.parse_args()

    retriever = get_retriever()
    result = retriever.ingest(force=args.force)

    print()
    print("=" * 55)
    print(" Runbook ingestion")
    print("=" * 55)
    print(f"  Result       : {result['message']}")
    print(f"  Ingested     : {result.get('ingested', 0)}")
    if result.get("existing_count"):
        print(f"  Existing     : {result['existing_count']}")


if __name__ == "__main__":
    main()