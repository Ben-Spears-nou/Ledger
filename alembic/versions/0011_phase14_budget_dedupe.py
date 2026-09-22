"""Phase 14 dedupe budget rows and add unique budget indexes.

Revision ID: 0011_phase14_budget_dedupe
Revises: 0010_phase13_work_plan
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0011_phase14_budget_dedupe"
down_revision: str | None = "0010_phase13_work_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql``; it dedupes budgets before the unique indexes."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0011_phase14_budget_dedupe is not supported")
