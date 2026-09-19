"""Pipeline forecast nodes (Phase 6). Not remaining money (D32)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class PipelineKind(Base):
    """Lookup: next_phase, commercial, proposal, other."""

    __tablename__ = "pipeline_kind"

    kind_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class PipelineNode(Base):
    """Named future cents on an award. Never remaining-to-spend (D32)."""

    __tablename__ = "pipeline_node"

    pipeline_node_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    kind_code: Mapped[str] = mapped_column(
        Text, ForeignKey("pipeline_kind.kind_code"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_date: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
