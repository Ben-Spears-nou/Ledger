"""Pydantic payloads for glossary, contract schedule, and Gantt (Phase 12)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GlossaryTermOut(BaseModel):
    """One Ledger word plus aliases."""

    term_code: str
    title: str
    definition: str
    href: str
    aliases: list[str] = Field(default_factory=list)


class ScheduleDraftIn(BaseModel):
    """One proposed or confirmed schedule row."""

    kind_code: str
    title: str
    start_date: str | None = None
    due_date: str
    notes: str | None = None
    origin_code: str = "manual"
    source_document_id: int | None = None
    keep: bool = True


class ScheduleProposeIn(BaseModel):
    """Ask for a draft; does not write rows."""

    document_id: int | None = None
    text: str | None = None


class ScheduleItemOut(BaseModel):
    """Stored or draft schedule row."""

    schedule_item_id: int | None = None
    award_id: int
    kind_code: str
    title: str
    start_date: str | None
    due_date: str
    status_code: str
    notes: str | None
    completed_at: str | None
    source_document_id: int | None
    origin_code: str
    created_at: str | None = None
    keep: bool = True


class ScheduleProposeOut(BaseModel):
    """Draft list the operator edits, then confirms."""

    award_id: int
    notes: list[str] = Field(default_factory=list)
    items: list[ScheduleItemOut] = Field(default_factory=list)


class ScheduleConfirmIn(BaseModel):
    """Rows to insert after the operator reviews the draft."""

    items: list[ScheduleDraftIn]


class SchedulePatch(BaseModel):
    """Edit a confirmed row."""

    title: str | None = None
    kind_code: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    status_code: str | None = None
    notes: str | None = None


class GanttBarOut(BaseModel):
    """One bar on the computed Gantt (D48)."""

    schedule_item_id: int
    award_id: int
    award_short_code: str
    title: str
    kind_code: str
    start_date: str
    due_date: str
    status_code: str
    lane: str
    offset_pct: int
    width_pct: int


class GanttOut(BaseModel):
    """Gantt window and bars for one or all awards."""

    as_of: str
    chart_start: str | None
    chart_end: str | None
    bars: list[GanttBarOut] = Field(default_factory=list)
