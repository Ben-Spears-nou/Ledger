"""Phase 1 database: schema, FKs, views, models, Alembic."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ledger.config import PROJECT_ROOT, get_settings
from ledger.db.engine import get_engine
from ledger.db.sql import declared_objects
from ledger.models import Base

REQUIRED_TABLES = {
    "organization",
    "person",
    "person_rate",
    "user_account",
    "award",
    "award_mod",
    "clin",
    "award_rate_policy",
    "award_rate_override",
    "budget_version",
    "budget_line",
    "time_code",
    "timesheet_period",
    "timesheet_line",
    "charge",
    "audit_event",
    "task",
    "assignment",
    "person_capacity",
    "commitment",
    "instrument",
    "instrument_share",
}


def test_schema_sql_declares_the_phase1_freeze() -> None:
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    declared = declared_objects(script)
    assert REQUIRED_TABLES <= declared.tables
    assert "v_budget_remaining" in declared.views
    assert "v_budget_line_remaining" in declared.views


def test_db_init_creates_tables_fks_and_views(isolated_db: Path) -> None:
    engine = get_engine()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
        }
        views = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='view'"))
        }
        assert REQUIRED_TABLES <= tables
        assert "v_budget_remaining" in views
        columns = [row[1] for row in connection.execute(text("PRAGMA table_info(award)"))]
        assert "fee_pot_cents" in columns
        assert "enforce_ceiling" in columns
        user_cols = [row[1] for row in connection.execute(text("PRAGMA table_info(user_account)"))]
        assert "password_changed_at" in user_cols
        line_cols = [
            row[1] for row in connection.execute(text("PRAGMA table_info(timesheet_line)"))
        ]
        assert "task_id" in line_cols


def test_foreign_key_violation_raises(isolated_db: Path) -> None:
    engine = get_engine()
    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO award ("
            "organization_id, short_code, title, agency, instrument_code, "
            "mechanism_code, phase_code, type_code, status_code, pop_start, pop_end, "
            "enforce_ceiling, labor_incurred, fee_engine"
            ") VALUES (1, 'X', 'x', 'NIH', 'grant', 'SBIR', 'I', 'NOPE', 'active', "
            "'2026-01-01', '2026-12-31', 1, 1, 'fixed_pot')"
        )
        connection.commit()


def test_orm_tables_match_schema_sql() -> None:
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    sql_tables = declared_objects(script).tables
    orm_tables = set(Base.metadata.tables)
    assert sql_tables == orm_tables


def test_alembic_upgrade_on_empty_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "alembic.db"
    monkeypatch.setenv("LEDGER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LEDGER_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LEDGER_SECRET_KEY", "test-secret")
    get_settings.cache_clear()
    get_engine.cache_clear()

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")

    engine = get_engine()
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
        }
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert REQUIRED_TABLES <= tables
    assert "alembic_version" in tables
    assert version == "0005_phase4_commitments"
