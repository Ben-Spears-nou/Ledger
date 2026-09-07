"""Purchases, travel, and instrument-split commitments (Phase 4)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class Instrument(Base):
    """Shared cost allocated to awards by fixed percents (D26)."""

    __tablename__ = "instrument"

    instrument_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.organization_id"), nullable=False
    )
    short_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    category_code: Mapped[str] = mapped_column(
        Text, ForeignKey("budget_category.category_code"), nullable=False
    )
    status_code: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    effective_to: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class InstrumentShare(Base):
    """One award's share of an instrument. ``share_pct`` is D16 units."""

    __tablename__ = "instrument_share"

    instrument_share_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("instrument.instrument_id"), nullable=False
    )
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    share_pct: Mapped[int] = mapped_column(Integer, nullable=False)


class Commitment(Base):
    """Open committed money, or a posted/cancelled row (D25)."""

    __tablename__ = "commitment"

    commitment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    category_code: Mapped[str] = mapped_column(
        Text, ForeignKey("budget_category.category_code"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    vendor: Mapped[str | None] = mapped_column(Text)
    person_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("person.person_id"))
    effective_date: Mapped[str] = mapped_column(Text, nullable=False)
    trip_end: Mapped[str | None] = mapped_column(Text)
    expected_date: Mapped[str | None] = mapped_column(Text)
    instrument_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("instrument.instrument_id")
    )
    charge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("charge.charge_id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
