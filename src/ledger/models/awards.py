"""Awards, mods, CLINs, and dated rate policies."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class Award(Base):
    """One contract, grant, or internal pot."""

    __tablename__ = "award"

    award_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.organization_id"), nullable=False
    )
    short_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    agency: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_instrument.instrument_code"), nullable=False
    )
    mechanism_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_mechanism.mechanism_code"), nullable=False
    )
    phase_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_phase.phase_code"), nullable=False
    )
    type_code: Mapped[str] = mapped_column(Text, ForeignKey("award_type.type_code"), nullable=False)
    status_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_status.status_code"), nullable=False
    )
    pop_start: Mapped[str] = mapped_column(Text, nullable=False)
    pop_end: Mapped[str] = mapped_column(Text, nullable=False)
    funded_through: Mapped[str | None] = mapped_column(Text)
    awarded_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    funded_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_pot_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enforce_ceiling: Mapped[int] = mapped_column(Integer, nullable=False)
    labor_incurred: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_engine: Mapped[str] = mapped_column(Text, nullable=False)
    ceiling_warn_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    overrun_policy: Mapped[str] = mapped_column(Text, nullable=False, default="warn")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class AwardMod(Base):
    """A dated change to money or period of performance."""

    __tablename__ = "award_mod"

    award_mod_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    mod_number: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    awarded_cost_cents: Mapped[int | None] = mapped_column(Integer)
    funded_amount_cents: Mapped[int | None] = mapped_column(Integer)
    fee_pot_cents: Mapped[int | None] = mapped_column(Integer)
    pop_start: Mapped[str | None] = mapped_column(Text)
    pop_end: Mapped[str | None] = mapped_column(Text)
    funded_through: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class Clin(Base):
    """Optional CLIN / option line. Unexercised options are not remaining."""

    __tablename__ = "clin"

    clin_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    clin_number: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_option: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exercise_window_start: Mapped[str | None] = mapped_column(Text)
    exercise_window_end: Mapped[str | None] = mapped_column(Text)
    exercised_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class AwardRatePolicy(Base):
    """Effective-dated labor recipe for one award (D11)."""

    __tablename__ = "award_rate_policy"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    effective_to: Mapped[str | None] = mapped_column(Text)
    cost_basis_code: Mapped[str] = mapped_column(
        Text, ForeignKey("cost_basis.cost_basis_code"), nullable=False
    )
    fringe_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oh_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ga_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_in_burden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    labor_budget_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("budget_line.budget_line_id")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class AwardRateOverride(Base):
    """Per-person or per-labor-category loaded rate on a policy."""

    __tablename__ = "award_rate_override"

    override_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("award_rate_policy.policy_id"), nullable=False
    )
    person_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("person.person_id"))
    labor_category: Mapped[str | None] = mapped_column(Text)
    loaded_rate_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class FundingExpectation(Base):
    """Expected increment. Not remaining (D42)."""

    __tablename__ = "funding_expectation"

    funding_expectation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    expected_date: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
