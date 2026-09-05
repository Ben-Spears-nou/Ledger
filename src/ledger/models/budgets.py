"""Versioned budget trees."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class BudgetVersion(Base):
    """One labeled budget snapshot. Exactly one row per award is active."""

    __tablename__ = "budget_version"

    budget_version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class BudgetLine(Base):
    """Approved amount for one category on a budget version."""

    __tablename__ = "budget_line"

    budget_line_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("budget_version.budget_version_id"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(
        Text, ForeignKey("budget_category.category_code"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(Text)
    approved_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
