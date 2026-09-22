"""Controlled-vocabulary tables from ``db/schema.sql``."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class Organization(Base):
    """Single company record in v1 (D8)."""

    __tablename__ = "organization"

    organization_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class Role(Base):
    """``employee`` or ``admin``."""

    __tablename__ = "role"

    role_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class AwardInstrument(Base):
    """``contract``, ``grant``, or ``internal``."""

    __tablename__ = "award_instrument"

    instrument_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class AwardMechanism(Base):
    """``SBIR``, ``STTR``, or ``other``."""

    __tablename__ = "award_mechanism"

    mechanism_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class AwardPhase(Base):
    """SBIR/STTR phase code."""

    __tablename__ = "award_phase"

    phase_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class AwardType(Base):
    """Award type plus the default rules profile."""

    __tablename__ = "award_type"

    type_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enforce_ceiling: Mapped[int] = mapped_column(Integer, nullable=False)
    labor_incurred: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_engine: Mapped[str] = mapped_column(Text, nullable=False)
    ceiling_warn_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    overrun_policy: Mapped[str] = mapped_column(Text, nullable=False, default="warn")


class AwardStatus(Base):
    """``pipeline``, ``active``, or ``closed``."""

    __tablename__ = "award_status"

    status_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class CostBasis(Base):
    """How loaded labor is chosen from the rate recipe."""

    __tablename__ = "cost_basis"

    cost_basis_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class BudgetCategory(Base):
    """Editable budget-line category."""

    __tablename__ = "budget_category"

    category_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Agency(Base):
    """Growing list of agency names (D1)."""

    __tablename__ = "agency"

    agency_name: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class RatePolicyTemplate(Base):
    """Form-fill preset. Percents seed at 0 so we do not fabricate rates."""

    __tablename__ = "rate_policy_template"

    template_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    award_type_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_type.type_code"), nullable=False
    )
    cost_basis_code: Mapped[str] = mapped_column(
        Text, ForeignKey("cost_basis.cost_basis_code"), nullable=False
    )
    fringe_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oh_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ga_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_in_burden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BudgetTemplateLine(Base):
    """Default budget lines for an award type."""

    __tablename__ = "budget_template_line"

    budget_template_line_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_type_code: Mapped[str] = mapped_column(
        Text, ForeignKey("award_type.type_code"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(
        Text, ForeignKey("budget_category.category_code"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
