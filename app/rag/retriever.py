"""Hybrid retriever — vector + BM25 + RRF + cross-encoder reranker."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.config import get_settings
from app.logging_config import get_logger
from app.rag.runbooks import RunbookChunk, load_all_runbooks

logger = get_logger("rag.retriever")

COLLECTION_NAME = "runbooks"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class RetrievedChunk:
    runbook_id: str
    title: str
    section: str
    content: str
    score: float


@lru_cache(maxsize=1)
def _embedder() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


class RunbookRetriever:
    """Lazy-loaded hybrid retriever."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: chromadb.ClientAPI | None = None
        self._collection = None
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[RunbookChunk] = []
        self._reranker: CrossEncoder | None = None

    @property
    def client(self):
        if self._client is None:
            persist = str(self.settings.chroma_persist_dir)
            Path(persist).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=persist,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    @property
    def reranker(self) -> CrossEncoder:
        if self._reranker is None:
            logger.info("loading_reranker", model=RERANKER_MODEL)
            self._reranker = CrossEncoder(RERANKER_MODEL)
        return self._reranker

    def is_ingested(self) -> bool:
        try:
            return self.collection.count() > 0
        except Exception:
            return False

    def ingest(self, force: bool = False) -> dict:
        chunks = load_all_runbooks()
        if not chunks:
            return {"ingested": 0, "message": "no runbook files found"}

        if self.is_ingested() and not force:
            return {
                "ingested": 0,
                "message": "already ingested",
                "existing_count": self.collection.count(),
            }

        if force:
            try:
                self.client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            self._collection = None

        texts = [c.content for c in chunks]
        embeddings = _embedder().encode(texts, normalize_embeddings=True).tolist()

        self.collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=texts,
            embeddings=embeddings,
            metadatas=[
                {"runbook_id": c.runbook_id, "title": c.title, "section": c.section}
                for c in chunks
            ],
        )

        self._bm25_chunks = chunks
        self._bm25 = BM25Okapi([c.content.lower().split() for c in chunks])

        logger.info("runbooks_ingested", count=len(chunks))
        return {"ingested": len(chunks), "message": "ok"}

    def _ensure_bm25(self) -> None:
        if self._bm25 is not None:
            return
        chunks = load_all_runbooks()
        self._bm25_chunks = chunks
        if chunks:
            self._bm25 = BM25Okapi([c.content.lower().split() for c in chunks])

    def _vector_search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        try:
            q = _embedder().encode([query], normalize_embeddings=True).tolist()[0]
            res = self.collection.query(query_embeddings=[q], n_results=top_k)
            if not res["ids"] or not res["ids"][0]:
                return []
            return list(zip(res["ids"][0], res["distances"][0]))
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e)[:200])
            return []

    def _bm25_search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        self._ensure_bm25()
        if not self._bm25 or not self._bm25_chunks:
            return []
        scores = self._bm25.get_scores(query.lower().split())
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            (self._bm25_chunks[i].chunk_id, float(s))
            for i, s in indexed
            if s > 0
        ]

    @staticmethod
    def rrf_fuse(
        ranked_lists: list[list[tuple[str, float]]], k: int = 60
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank, (chunk_id, _) in enumerate(ranked, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        vec = self._vector_search(query, top_k * 2)
        bm25 = self._bm25_search(query, top_k * 2)
        fused = self.rrf_fuse([vec, bm25])[: top_k * 2]
        if not fused:
            return []

        self._ensure_bm25()
        by_id = {c.chunk_id: c for c in self._bm25_chunks}
        candidates = [(by_id[cid], rrf) for cid, rrf in fused if cid in by_id]
        if not candidates:
            return []

        try:
            pairs = [[query, c.content] for c, _ in candidates]
            rerank_scores = list(self.reranker.predict(pairs))
        except Exception as e:
            logger.warning("reranker_failed", error=str(e)[:200])
            rerank_scores = [rrf for _, rrf in candidates]

        ranked = sorted(
            zip(candidates, rerank_scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )[:top_k]

        return [
            RetrievedChunk(
                runbook_id=c.runbook_id,
                title=c.title,
                section=c.section,
                content=c.content,
                score=float(score),
            )
            for (c, _), score in ranked
        ]


@lru_cache(maxsize=1)
def get_retriever() -> RunbookRetriever:
    return RunbookRetriever()