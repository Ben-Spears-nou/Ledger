"""People, dated base rates, and login accounts."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class Person(Base):
    """A human who can charge time or own a login."""

    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.organization_id"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    hire_date: Mapped[str | None] = mapped_column(Text)
    term_date: Mapped[str | None] = mapped_column(Text)
    labor_category: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class PersonRate(Base):
    """Effective-dated base rate. Written in Phase 2."""

    __tablename__ = "person_rate"

    person_rate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(Integer, ForeignKey("person.person_id"), nullable=False)
    effective_from: Mapped[str] = mapped_column(Text, nullable=False)
    effective_to: Mapped[str | None] = mapped_column(Text)
    base_rate_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_per_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())


class UserAccount(Base):
    """Login bound to one person and one role."""

    __tablename__ = "user_account"

    user_account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("person.person_id"), nullable=False, unique=True
    )
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_code: Mapped[str] = mapped_column(Text, ForeignKey("role.role_code"), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    password_changed_at: Mapped[str | None] = mapped_column(Text)
