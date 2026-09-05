"""Tasks, assignments, and dated person capacity (Phase 3)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class Task(Base):
    """Work package on one award. Not a charge code (D22)."""

    __tablename__ = "task"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    short_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class Assignment(Base):
    """Dated planned hours/week. Prefills drafts; does not post (D23)."""

    __tablename__ = "assignment"

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(Integer, ForeignKey("person.person_id"), nullable=False)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("task.task_id"))
    hours_hundredths_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    effective_to: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class PersonCapacity(Base):
    """Dated available hours/week. Informational; not a timesheet rule (D24)."""

    __tablename__ = "person_capacity"

    person_capacity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(Integer, ForeignKey("person.person_id"), nullable=False)
    hours_hundredths_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    effective_to: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
