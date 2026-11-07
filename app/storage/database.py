"""SQLite database setup for telemetry storage."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            future=True,
        )
    return _session_factory


def get_session() -> Iterator[Session]:
    """FastAPI dependency — yields a session per request."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    from app.storage import models  # noqa: F401
    Base.metadata.create_all(bind=get_engine())


def reset_engine() -> None:
    """For tests — clears cached engine/session factory."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None