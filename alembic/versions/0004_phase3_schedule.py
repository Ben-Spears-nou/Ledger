"""Phase 3 schedule: task, assignment, person_capacity, timesheet_line.task_id.

Revision ID: 0004_phase3_schedule
Revises: 0003_phase25_share
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import ensure_phase3_schema, ensure_share_readiness_schema
from ledger.db.sql import as_idempotent_seed, is_seed_statement, iter_sql_statements

revision: str = "0004_phase3_schedule"
down_revision: str | None = "0003_phase25_share"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` and add columns CREATE TABLE will not alter."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    connection = op.get_bind()
    for statement in iter_sql_statements(script):
        sql = as_idempotent_seed(statement) if is_seed_statement(statement) else statement
        connection.exec_driver_sql(sql)
    ensure_share_readiness_schema(connection)
    ensure_phase3_schema(connection)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0004_phase3_schedule is not supported")
