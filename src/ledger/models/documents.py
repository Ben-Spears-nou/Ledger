"""Award document register and compliance due dates (Phase 5)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ledger.models.base import Base, now_default


class DocumentKind(Base):
    """Lookup: contract, mod, report, invoice, correspondence, other."""

    __tablename__ = "document_kind"

    kind_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class ComplianceKind(Base):
    """Lookup for compliance obligations."""

    __tablename__ = "compliance_kind"

    kind_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class ComplianceStatus(Base):
    """``open``, ``done``, or ``waived``."""

    __tablename__ = "compliance_status"

    status_code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class Document(Base):
    """Metadata row; optional file on local disk (D29)."""

    __tablename__ = "document"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    kind_code: Mapped[str] = mapped_column(
        Text, ForeignKey("document_kind.kind_code"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_date: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    stored_ext: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )


class ComplianceItem(Base):
    """Dated obligation on an award (D30). Not remaining money."""

    __tablename__ = "compliance_item"

    compliance_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey("award.award_id"), nullable=False)
    kind_code: Mapped[str] = mapped_column(
        Text, ForeignKey("compliance_kind.kind_code"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[str] = mapped_column(
        Text, ForeignKey("compliance_status.status_code"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document.document_id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=now_default())
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user_account.user_account_id")
    )
