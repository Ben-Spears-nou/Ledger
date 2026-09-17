"""SOW work-plan and progress-Gantt payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkPlanDraftIn(BaseModel):
    """One proposed, confirmed, or manually added requirement."""

    requirement_code: str | None = None
    title: str
    start_date: str
    due_date: str
    percent_complete_bp: int = Field(default=0, ge=0, le=10000)
    notes: str | None = None
    source_document_id: int | None = None
    origin_code: str = "manual"
    sort_order: int = 0
    keep: bool = True


class WorkPlanProposeIn(BaseModel):
    """Extract an editable SOW work-plan draft."""

    document_id: int | None = None
    text: str | None = None


class WorkPlanItemOut(BaseModel):
    """Stored or proposed work-plan requirement."""

    work_plan_item_id: int | None = None
    award_id: int
    requirement_code: str | None
    title: str
    start_date: str
    due_date: str
    percent_complete_bp: int
    notes: str | None
    source_document_id: int | None
    origin_code: str
    sort_order: int
    created_at: str | None = None
    keep: bool = True


class WorkPlanProposeOut(BaseModel):
    """Draft requirements and extraction notes."""

    award_id: int
    notes: list[str] = Field(default_factory=list)
    items: list[WorkPlanItemOut] = Field(default_factory=list)


class WorkPlanConfirmIn(BaseModel):
    """Rows selected for insertion."""

    items: list[WorkPlanDraftIn]


class WorkPlanPatch(BaseModel):
    """Editable work-plan fields, including progress."""

    requirement_code: str | None = None
    title: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    percent_complete_bp: int | None = Field(default=None, ge=0, le=10000)
    notes: str | None = None
    sort_order: int | None = None


class WorkGanttBarOut(BaseModel):
    """One work-plan bar with schedule and completion geometry."""

    work_plan_item_id: int
    award_id: int
    award_short_code: str
    requirement_code: str | None
    title: str
    start_date: str
    due_date: str
    percent_complete_bp: int
    lane: str
    offset_pct: int
    width_pct: int
    complete_width_pct: int


class WorkGanttOut(BaseModel):
    """Computed progress Gantt."""

    as_of: str
    chart_start: str | None
    chart_end: str | None
    bars: list[WorkGanttBarOut] = Field(default_factory=list)
