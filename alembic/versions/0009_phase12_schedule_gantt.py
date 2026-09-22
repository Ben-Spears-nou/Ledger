"""Phase 12 glossary, contract schedule, and Gantt.

Revision ID: 0009_phase12_schedule_gantt
Revises: 0008_phase10_operations
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0009_phase12_schedule_gantt"
down_revision: str | None = "0008_phase10_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so Phase 12 tables land."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0009_phase12_schedule_gantt is not supported")
