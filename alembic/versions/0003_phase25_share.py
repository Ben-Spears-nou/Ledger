"""Phase 2.5 share-readiness: audit_event and password_changed_at.

Revision ID: 0003_phase25_share
Revises: 0002_phase2
Create Date: 2026-09-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import ensure_share_readiness_schema
from ledger.db.sql import as_idempotent_seed, is_seed_statement, iter_sql_statements

revision: str = "0003_phase25_share"
down_revision: str | None = "0002_phase2"
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


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0003_phase25_share is not supported")
