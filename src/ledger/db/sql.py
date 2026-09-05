"""Split and classify statements from ``db/schema.sql``."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass

_COMMENT_LINE = re.compile(r"^\s*--")
_INSERT_INTO = re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)
_OBJECT_NAME = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SchemaObjects:
    """Names of the objects a SQL script creates, grouped by kind."""

    tables: frozenset[str]
    indexes: frozenset[str]
    views: frozenset[str]


def _strip_leading_comments(statement: str) -> str:
    """Drop leading comment and blank lines from a statement."""
    lines = statement.splitlines()
    while lines and (not lines[0].strip() or _COMMENT_LINE.match(lines[0])):
        lines.pop(0)
    return "\n".join(lines).strip()


def iter_sql_statements(script: str) -> Iterator[str]:
    """Yield complete SQL statements from a script, discarding comment-only text."""
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = _strip_leading_comments(buffer)
            if statement:
                yield statement
            buffer = ""
    trailing = _strip_leading_comments(buffer)
    if trailing:
        yield trailing


def is_seed_statement(statement: str) -> bool:
    """Report whether a statement inserts rows (as opposed to defining schema)."""
    return statement.upper().lstrip().startswith("INSERT")


def as_idempotent_seed(statement: str) -> str:
    """Rewrite an ``INSERT INTO`` as ``INSERT OR IGNORE INTO``."""
    return _INSERT_INTO.sub("INSERT OR IGNORE INTO", statement, count=1)


def declared_objects(script: str) -> SchemaObjects:
    """Collect the table, index, and view names a script declares."""
    found: dict[str, set[str]] = {"TABLE": set(), "INDEX": set(), "VIEW": set()}
    for statement in iter_sql_statements(script):
        match = _OBJECT_NAME.search(statement)
        if not match:
            continue
        kind = match.group(1).upper().replace("UNIQUE INDEX", "INDEX")
        found[kind].add(match.group(2))
    return SchemaObjects(
        tables=frozenset(found["TABLE"]),
        indexes=frozenset(found["INDEX"]),
        views=frozenset(found["VIEW"]),
    )
