"""Phase 15 award-type fee rules and FFP monthly billing.

Revision ID: 0012_phase15_ffp_billing
Revises: 0011_phase14_budget_dedupe
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql

revision: str = "0012_phase15_ffp_billing"
down_revision: str | None = "0011_phase14_budget_dedupe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add FFP fee fields and persisted working-month billing periods."""
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    connection = op.get_bind()
    apply_schema_sql(connection, script)

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from ledger.models import Award, AwardRatePolicy, BudgetLine, BudgetVersion
    from ledger.services.awards import _ffp_fee_cents, _rebuild_ffp_billing_schedule

    session = Session(bind=connection)
    for award in session.scalars(select(Award).where(Award.type_code == "FFP")):
        policy = session.scalar(
            select(AwardRatePolicy)
            .where(
                AwardRatePolicy.award_id == award.award_id,
                AwardRatePolicy.effective_to.is_(None),
            )
            .order_by(AwardRatePolicy.effective_from.desc())
        )
        if policy is not None and award.fee_pct == 0:
            award.fee_pct = policy.fee_pct
        if policy is not None:
            policy.fee_pct = 0
            policy.fee_in_burden = 0
        award.fee_pot_cents = _ffp_fee_cents(award.funded_amount_cents, award.fee_pct)

        version = session.scalar(
            select(BudgetVersion).where(
                BudgetVersion.award_id == award.award_id,
                BudgetVersion.is_active == 1,
            )
        )
        if version is not None:
            fee_line = session.scalar(
                select(BudgetLine).where(
                    BudgetLine.budget_version_id == version.budget_version_id,
                    BudgetLine.category_code == "fee",
                )
            )
            if fee_line is None:
                session.add(
                    BudgetLine(
                        budget_version_id=version.budget_version_id,
                        category_code="fee",
                        label="Fee / profit",
                        approved_cents=award.fee_pot_cents,
                        sort_order=60,
                    )
                )
            else:
                fee_line.approved_cents = award.fee_pot_cents
        _rebuild_ffp_billing_schedule(session, award, actor_id=None)
    session.flush()


def downgrade() -> None:
    """Not supported."""
    raise NotImplementedError("downgrade of 0012_phase15_ffp_billing is not supported")
