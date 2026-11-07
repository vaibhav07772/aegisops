"""Exact-hash LLM cache (SQLite-backed) to reduce cost and latency.

Note on naming: originally a *semantic* cache using vector similarity was
attempted (all-MiniLM-L6-v2 embeddings), but it proved unreliable for
structured prompts where only numerical values differ — different scenarios
were being treated as identical (cosine similarity ~1.0) and cross-scenario
contamination occurred.

This implementation uses EXACT SHA256 hash matching of (system_prompt + prompt).
It gives deterministic behavior: same input → same cache hit; different
scenario → different hash → fresh LLM call.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

from app.config import get_settings
from app.logging_config import get_logger
from app.monitoring import metrics as prom

logger = get_logger("llm.cache")

DEFAULT_TTL_SECONDS = 3600  # 1 hour


class SemanticCache:
    """Kept class name for backward compat. Uses exact-hash SQLite cache."""

    def __init__(self) -> None:
        settings = get_settings()
        db_path = Path(settings.data_dir) / "llm_cache.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    cache_id TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, prompt: str, system_prompt: str = "") -> str | None:
        """Return cached response for EXACT same input, or None."""
        full_text = f"{system_prompt}\n\n{prompt}"
        cache_id = self._hash(full_text)
        with self._conn() as c:
            row = c.execute(
                "SELECT response, expires_at FROM cache WHERE cache_id = ?",
                (cache_id,),
            ).fetchone()

        if not row:
            prom.llm_cache_total.labels(result="miss").inc()
            return None

        if time.time() > row["expires_at"]:
            prom.llm_cache_total.labels(result="miss_expired").inc()
            return None

        prom.llm_cache_total.labels(result="hit").inc()
        logger.info("cache_hit", prompt_len=len(full_text))
        return row["response"]

    def set(
        self,
        prompt: str,
        system_prompt: str,
        response: str,
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        full_text = f"{system_prompt}\n\n{prompt}"
        cache_id = self._hash(full_text)
        now = time.time()
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO cache
                    (cache_id, response, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_id, response, now + ttl, now),
            )

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM cache")
        logger.info("cache_cleared")

    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            active = c.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (time.time(),)
            ).fetchone()[0]
        return {"total": total, "active": active}

    def prune_expired(self) -> int:
        with self._conn() as c:
            deleted = c.execute(
                "DELETE FROM cache WHERE expires_at <= ?", (time.time(),)
            ).rowcount
        return deleted


_cache_instance: SemanticCache | None = None


def get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance