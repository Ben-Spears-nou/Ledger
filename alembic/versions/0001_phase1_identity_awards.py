"""Phase 1 identity, awards, rate policies, and budgets.

Applies ``db/schema.sql`` (the source of truth) so Alembic head matches
``db-init``.

Revision ID: 0001_phase1
Revises:
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.sql import as_idempotent_seed, is_seed_statement, iter_sql_statements

revision: str = "0001_phase1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Execute ``db/schema.sql`` on the bound connection."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    connection = op.get_bind()
    for statement in iter_sql_statements(script):
        sql = as_idempotent_seed(statement) if is_seed_statement(statement) else statement
        connection.exec_driver_sql(sql)


def downgrade() -> None:
    """Not supported: drop the database file instead."""
    raise NotImplementedError("downgrade of 0001_phase1 is not supported")
