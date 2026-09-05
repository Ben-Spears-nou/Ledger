"""Build the database by executing ``db/schema.sql``.

The SQL file is the source of truth. Running twice is safe: DDL uses
``IF NOT EXISTS`` and seed ``INSERT``s are replayed as ``INSERT OR IGNORE``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from ledger.config import get_settings
from ledger.db.engine import create_db_engine, resolve_db_url
from ledger.db.sql import (
    SchemaObjects,
    as_idempotent_seed,
    is_seed_statement,
    iter_sql_statements,
)


@dataclass
class BootstrapResult:
    """Outcome of a ``db-init`` run."""

    database: str
    created: bool
    tables: list[str] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    seeded_statements: int = 0

    def summary(self) -> str:
        """Return a one-line human summary."""
        action = "created" if self.created else "verified"
        return (
            f"{action} {self.database}: {len(self.tables)} tables, "
            f"{len(self.indexes)} indexes, {len(self.views)} views, "
            f"{self.seeded_statements} seed statements applied"
        )


def existing_objects(engine: Engine) -> SchemaObjects:
    """Read the object names currently present in the database."""
    query = text(
        "SELECT type, name FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' AND type IN ('table','index','view')"
    )
    found: dict[str, set[str]] = {"table": set(), "index": set(), "view": set()}
    with engine.connect() as connection:
        for kind, name in connection.execute(query):
            found[kind].add(name)
    return SchemaObjects(
        tables=frozenset(found["table"]),
        indexes=frozenset(found["index"]),
        views=frozenset(found["view"]),
    )


def ensure_share_readiness_schema(connection: Connection) -> None:
    """Add Phase 2.5 columns that ``CREATE TABLE IF NOT EXISTS`` will not alter.

    Existing Phase 2 databases already have ``user_account`` without
    ``password_changed_at``. Fresh installs get the column from ``schema.sql``.
    """
    rows = connection.exec_driver_sql("PRAGMA table_info(user_account)").fetchall()
    names = {row[1] for row in rows}
    if "password_changed_at" not in names:
        connection.exec_driver_sql("ALTER TABLE user_account ADD COLUMN password_changed_at TEXT")


def ensure_phase3_schema(connection: Connection) -> None:
    """Add ``timesheet_line.task_id`` that ``CREATE TABLE IF NOT EXISTS`` will not alter.

    New tables (``task``, ``assignment``, ``person_capacity``) come from
    ``schema.sql``. Existing Phase 2.5 databases already have ``timesheet_line``
    without ``task_id``.
    """
    rows = connection.exec_driver_sql("PRAGMA table_info(timesheet_line)").fetchall()
    if not rows:
        return
    names = {row[1] for row in rows}
    if "task_id" not in names:
        connection.exec_driver_sql(
            "ALTER TABLE timesheet_line ADD COLUMN task_id INTEGER REFERENCES task (task_id)"
        )


def is_initialized(engine: Engine) -> bool:
    """Report whether the core award table already exists."""
    return "award" in existing_objects(engine).tables


def _require_sqlite(engine: Engine) -> None:
    """Reject non-SQLite engines, which must be migrated with Alembic instead."""
    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            f"db/schema.sql is SQLite DDL; cannot execute it against "
            f"'{engine.dialect.name}'. Use Alembic migrations for that backend."
        )


def init_db(
    engine: Engine | None = None,
    *,
    schema_path: Path | None = None,
    force: bool = False,
    seed_admin: bool = True,
) -> BootstrapResult:
    """Create or verify the database described by ``db/schema.sql``."""
    settings = get_settings()
    engine = engine or create_db_engine()
    _require_sqlite(engine)
    script = (schema_path or settings.schema_path).read_text(encoding="utf-8")

    database = engine.url.database or ":memory:"
    if database not in {":memory:", None} and database != "":
        Path(str(database)).parent.mkdir(parents=True, exist_ok=True)

    if force:
        _drop_all(engine)

    created = not is_initialized(engine)
    seeded = 0
    with engine.begin() as connection:
        for statement in iter_sql_statements(script):
            if is_seed_statement(statement):
                connection.exec_driver_sql(as_idempotent_seed(statement))
                seeded += 1
            else:
                connection.exec_driver_sql(statement)
        ensure_share_readiness_schema(connection)
        ensure_phase3_schema(connection)

    if seed_admin:
        from ledger.db.seed import ensure_bootstrap_admin

        ensure_bootstrap_admin(engine)

    present = existing_objects(engine)
    return BootstrapResult(
        database=str(database),
        created=created,
        tables=sorted(present.tables),
        indexes=sorted(present.indexes),
        views=sorted(present.views),
        seeded_statements=seeded,
    )


def _drop_all(engine: Engine) -> None:
    """Drop every view and table in the database."""
    present = existing_objects(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for view in sorted(present.views):
            connection.exec_driver_sql(f'DROP VIEW IF EXISTS "{view}"')
        for table in sorted(present.tables):
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def init_database() -> Path | None:
    """Compatibility wrapper used by ``tasks.py`` and older Phase 0 tests."""
    settings = get_settings()
    settings.runtime_dir().mkdir(parents=True, exist_ok=True)
    result = init_db()
    print(result.summary(), flush=True)
    return settings.resolved_db_path()


def main(argv: list[str] | None = None) -> int:
    """CLI entry for ``python -m ledger.db.bootstrap``."""
    import argparse

    parser = argparse.ArgumentParser(description="Build the Ledger database from db/schema.sql")
    parser.add_argument(
        "--force",
        action="store_true",
        help="drop existing tables/views before rebuilding (destroys data)",
    )
    args = parser.parse_args(argv)
    print(f"database url: {resolve_db_url()}")
    result = init_db(force=args.force)
    print(result.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
