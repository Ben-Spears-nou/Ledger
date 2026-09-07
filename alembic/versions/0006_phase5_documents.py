"""Phase 5 documents and compliance items.

Revision ID: 0006_phase5_documents
Revises: 0005_phase4_commitments
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0006_phase5_documents"
down_revision: str | None = "0005_phase4_commitments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so document tables land after ALTERs/indexes."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0006_phase5_documents is not supported")
