"""Declarative base and shared column conventions.

Models mirror ``db/schema.sql`` exactly. Literal SQL types (``TEXT``,
``INTEGER``) keep Alembic autogenerate quiet about spurious type differences.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import TextClause


class Base(DeclarativeBase):
    """Base class for every Ledger model."""


def now_default() -> TextClause:
    """Server default matching ``DEFAULT (datetime('now'))`` in the schema."""
    return text("(datetime('now'))")
