"""Phase 10 operations: overrun policy, expected dates, funding expectations.

Revision ID: 0008_phase10_operations
Revises: 0007_phase6_pipeline_burn
Create Date: 2026-09-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0008_phase10_operations"
down_revision: str | None = "0007_phase6_pipeline_burn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so Phase 10 columns and tables land."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0008_phase10_operations is not supported")
