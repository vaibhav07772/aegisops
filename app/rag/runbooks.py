"""Runbook markdown parser + chunker."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger("rag.runbooks")


@dataclass
class RunbookChunk:
    chunk_id: str
    runbook_id: str
    title: str
    section: str
    content: str


def parse_markdown_runbook(path: Path) -> list[RunbookChunk]:
    text = path.read_text(encoding="utf-8")
    runbook_id = path.stem

    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else runbook_id

    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
    chunks: list[RunbookChunk] = []
    for i, section in enumerate(sections[1:], start=1):
        lines = section.split("\n", 1)
        section_title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if not body:
            continue
        chunks.append(
            RunbookChunk(
                chunk_id=f"{runbook_id}::s{i}",
                runbook_id=runbook_id,
                title=title,
                section=section_title,
                content=f"## {section_title}\n\n{body}",
            )
        )
    return chunks


def load_all_runbooks(runbooks_dir: Path | None = None) -> list[RunbookChunk]:
    if runbooks_dir is None:
        runbooks_dir = get_settings().runbooks_dir
    if not runbooks_dir.exists():
        logger.warning("runbooks_dir_missing", path=str(runbooks_dir))
        return []
    chunks: list[RunbookChunk] = []
    for path in sorted(runbooks_dir.glob("*.md")):
        try:
            chunks.extend(parse_markdown_runbook(path))
        except Exception:
            logger.exception("runbook_parse_failed", path=str(path))
    return chunks