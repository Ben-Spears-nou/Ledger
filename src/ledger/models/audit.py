"""Append-only audit events (D19). Do not update or delete rows."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class AuditEvent(Base):
    """One recorded action. Phase 7 is the UI; this table is Phase 2.5."""

    __tablename__ = "audit_event"

    audit_event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
