"""Timesheets and posted labor charges."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class TimeCode(Base):
    """Award vs company time buckets (PTO, holiday, IR&D, B&P)."""

    __tablename__ = "time_code"

    time_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    consumes_award: Mapped[int] = mapped_column(Integer, nullable=False)


class TimesheetPeriod(Base):
    """One person's calendar week. Status only; hours live on lines."""

    __tablename__ = "timesheet_period"

    timesheet_period_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(Integer, ForeignKey("person.person_id"), nullable=False)
    week_start: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[str] = mapped_column(Text, nullable=False)
    return_comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class TimesheetLine(Base):
    """Hours on one day for one award or time code."""

    __tablename__ = "timesheet_line"

    timesheet_line_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timesheet_period_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("timesheet_period.timesheet_period_id"), nullable=False
    )
    work_date: Mapped[str] = mapped_column(Text, nullable=False)
    hours_hundredths: Mapped[int] = mapped_column(Integer, nullable=False)
    time_code: Mapped[str] = mapped_column(Text, ForeignKey("time_code.time_code"), nullable=False)
    award_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("award.award_id"))
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("task.task_id"))


class Charge(Base):
    """Posted money fact. Labor snapshots the rate stack used (D5)."""

    __tablename__ = "charge"

    charge_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    timesheet_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("timesheet_line.timesheet_line_id")
    )
    award_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("award.award_id"))
    budget_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("budget_line.budget_line_id")
    )
    category_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("budget_category.category_code")
    )
    person_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("person.person_id"))
    work_date: Mapped[str | None] = mapped_column(Text)
    hours_hundredths: Mapped[int | None] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rate_cents: Mapped[int | None] = mapped_column(Integer)
    fringe_pct: Mapped[int | None] = mapped_column(Integer)
    oh_pct: Mapped[int | None] = mapped_column(Integer)
    ga_pct: Mapped[int | None] = mapped_column(Integer)
    fee_pct: Mapped[int | None] = mapped_column(Integer)
    fee_in_burden: Mapped[int | None] = mapped_column(Integer)
    loaded_rate_cents: Mapped[int | None] = mapped_column(Integer)
    person_rate_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("person_rate.person_rate_id")
    )
    policy_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("award_rate_policy.policy_id")
    )
    override_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("award_rate_override.override_id")
    )
    reverses_charge_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("charge.charge_id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
