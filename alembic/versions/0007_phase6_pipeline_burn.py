"""Phase 6 pipeline nodes and monthly burn view.

Revision ID: 0007_phase6_pipeline_burn
Revises: 0006_phase5_documents
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0007_phase6_pipeline_burn"
down_revision: str | None = "0006_phase5_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so pipeline tables and the burn view land."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0007_phase6_pipeline_burn is not supported")
