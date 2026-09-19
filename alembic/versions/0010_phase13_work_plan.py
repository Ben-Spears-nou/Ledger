"""Phase 13 SOW work plan and progress Gantt.

Revision ID: 0010_phase13_work_plan
Revises: 0009_phase12_schedule_gantt
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0010_phase13_work_plan"
down_revision: str | None = "0009_phase12_schedule_gantt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-apply ``db/schema.sql`` so the work-plan table lands."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    apply_schema_sql(op.get_bind(), script)


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0010_phase13_work_plan is not supported")
