"""Glossary and contract schedule (Phase 12). Not remaining money."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class GlossaryTerm(Base):
    """Ledger word plus a help link (D46)."""

    __tablename__ = "glossary_term"

    term_code: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    href: Mapped[str] = mapped_column(Text, nullable=False)


class GlossaryAlias(Base):
    """Everyday phrase mapped onto a glossary term."""

    __tablename__ = "glossary_alias"

    alias: Mapped[str] = mapped_column(Text, primary_key=True)
    term_code: Mapped[str] = mapped_column(
        Text, ForeignKey("glossary_term.term_code"), nullable=False
    )


class ScheduleKind(Base):
    """milestone, deliverable, report, pop, other."""

    __tablename__ = "schedule_kind"

    kind_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class ScheduleItem(Base):
    """Confirmed dated contract work on an award (D47)."""

    __tablename__ = "schedule_item"

    schedule_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    kind_code: Mapped[str] = mapped_column(
        Text, ForeignKey("schedule_kind.kind_code"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[str] = mapped_column(
        Text, ForeignKey("compliance_status.status_code"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document.document_id")
    )
    origin_code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
