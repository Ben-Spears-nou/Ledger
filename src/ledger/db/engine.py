"""Engine and session plumbing.

``PRAGMA foreign_keys=ON`` is applied to every SQLite connection. A relative
SQLite path in ``LEDGER_DB_URL`` is resolved against the project root.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ledger.config import Settings, get_settings


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Turn on foreign-key enforcement for a freshly opened SQLite connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def resolve_db_url(settings: Settings | None = None) -> str:
    """Return the database URL with a relative SQLite path made absolute."""
    settings = settings or get_settings()
    db_path = settings.resolved_db_path()
    if db_path is None:
        return settings.db_url
    return f"sqlite:///{db_path.as_posix()}"


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create an engine with Ledger's connection invariants applied."""
    resolved = url or resolve_db_url()
    engine = create_engine(resolved, echo=echo, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine built from configuration."""
    return create_db_engine()


def get_sessionmaker(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine`` (default: the shared engine)."""
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Provide a transactional session scope, committing on success."""
    factory = get_sessionmaker(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
