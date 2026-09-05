"""Phase 2 timesheets and charges.

Revision ID: 0002_phase2
Revises: 0001_phase1
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.sql import as_idempotent_seed, is_seed_statement, iter_sql_statements

revision: str = "0002_phase2"
down_revision: str | None = "0001_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so new tables and views land idempotently."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    connection = op.get_bind()
    for statement in iter_sql_statements(script):
        sql = as_idempotent_seed(statement) if is_seed_statement(statement) else statement
        connection.exec_driver_sql(sql)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0002_phase2 is not supported")
