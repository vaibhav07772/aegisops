"""Tests for RAG runbook parsing + retrieval primitives."""
from __future__ import annotations

from pathlib import Path

from app.rag.retriever import RunbookRetriever
from app.rag.runbooks import load_all_runbooks, parse_markdown_runbook


def test_parse_markdown_runbook():
    path = Path("data/runbooks/memory_leak.md")
    assert path.exists(), "Runbook file missing"
    chunks = parse_markdown_runbook(path)
    assert len(chunks) >= 3
    sections = {c.section for c in chunks}
    assert any("Symptoms" in s for s in sections)
    assert any("Remediation" in s for s in sections)
    for c in chunks:
        assert c.runbook_id == "memory_leak"
        assert c.chunk_id.startswith("memory_leak::")
        assert c.content


def test_load_all_runbooks():
    chunks = load_all_runbooks()
    assert len(chunks) >= 20  # 6 runbooks × ~4 sections each
    ids = {c.runbook_id for c in chunks}
    assert "memory_leak" in ids
    assert "slow_database" in ids
    assert "cpu_spike" in ids
    assert "service_outage" in ids
    assert "error_cascade" in ids


def test_rrf_fusion_ranks_common_items_higher():
    list_a = [("x", 0.9), ("y", 0.8), ("z", 0.7)]
    list_b = [("y", 0.95), ("z", 0.85), ("w", 0.5)]
    fused = RunbookRetriever.rrf_fuse([list_a, list_b])

    ids = [cid for cid, _ in fused]
    assert "y" in ids and "z" in ids
    # y and z appear in both lists → ranked above x (only in one)
    assert ids.index("y") < ids.index("x")
    assert ids.index("z") < ids.index("x")


def test_rrf_empty_input():
    assert RunbookRetriever.rrf_fuse([]) == []
    assert RunbookRetriever.rrf_fuse([[], []]) == []


def test_retriever_init_does_not_load_models():
    """Constructing the retriever must NOT trigger model downloads."""
    r = RunbookRetriever()
    assert r._reranker is None
    assert r._client is None
    assert r._collection is None
    assert r._bm25 is None