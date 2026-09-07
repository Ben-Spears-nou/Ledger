"""Pydantic payloads for documents and compliance items."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """Register row without a file."""

    kind_code: str
    title: str
    document_date: str | None = None
    notes: str | None = None


class DocumentOut(BaseModel):
    """Admin document metadata. ``has_file`` is true when a file was stored."""

    document_id: int
    award_id: int
    kind_code: str
    title: str
    document_date: str | None
    notes: str | None
    original_filename: str | None
    content_type: str | None
    size_bytes: int | None
    has_file: bool
    created_at: str


class ComplianceCreate(BaseModel):
    """New due date on an award."""

    kind_code: str
    title: str
    due_date: str
    notes: str | None = None


class CompliancePatch(BaseModel):
    """Status change. ``done`` sets completed_at."""

    status_code: str | None = None
    notes: str | None = Field(default=None)
    document_id: int | None = None


class ComplianceOut(BaseModel):
    """Admin compliance row, including award identity for the calendar."""

    compliance_item_id: int
    award_id: int
    award_short_code: str | None = None
    kind_code: str
    title: str
    due_date: str
    status_code: str
    notes: str | None
    completed_at: str | None
    document_id: int | None = None
    created_at: str
