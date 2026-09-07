"""Pydantic payloads for home, staffing, search, and close (Phase 10)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannedHoursOut(BaseModel):
    """Employee-visible assignment hours for one week. No dollars."""

    award_id: int
    task_id: int | None = None
    hours_per_week: float


class MissingWeekOut(BaseModel):
    """Person who has not submitted the week."""

    person_id: int
    display_name: str
    username: str | None = None
    status_code: str | None = None


class HomeApprovalOut(BaseModel):
    """Submitted week waiting on the queue."""

    timesheet_period_id: int
    person_id: int
    display_name: str
    week_start: str
    hours_total: float


class HomeComplianceOut(BaseModel):
    """Open compliance due soon or overdue."""

    compliance_item_id: int
    award_id: int
    award_short_code: str
    title: str
    due_date: str
    status_code: str
    document_id: int | None = None


class HomeCommitmentOut(BaseModel):
    """Open commitment past expected/effective date."""

    commitment_id: int
    award_id: int
    award_short_code: str
    description: str | None
    amount_cents: int
    aging_date: str
    age_days: int


class CloseChecklistOut(BaseModel):
    """Month-close counts through the as-of week. Not a GL close."""

    as_of: str
    week_start: str
    missing_week_count: int
    draft_count: int
    submitted_count: int
    open_commitment_count: int


class PortfolioRowOut(BaseModel):
    """One award on the operations table."""

    award_id: int
    short_code: str
    title: str
    status_code: str
    type_code: str
    remaining_approved_cents: int
    remaining_funded_cents: int
    runway_days: int | None = None
    alert_codes: list[str] = Field(default_factory=list)
    next_compliance_due: str | None = None
    next_compliance_title: str | None = None
    overrun_policy: str


class HomeOut(BaseModel):
    """Admin Monday board (D40)."""

    as_of: str
    week_start: str
    missing_weeks: list[MissingWeekOut] = Field(default_factory=list)
    approvals: list[HomeApprovalOut] = Field(default_factory=list)
    compliance_due: list[HomeComplianceOut] = Field(default_factory=list)
    aging_commitments: list[HomeCommitmentOut] = Field(default_factory=list)
    close: CloseChecklistOut
    portfolio: list[PortfolioRowOut] = Field(default_factory=list)


class StaffingWeekOut(BaseModel):
    """One person's hours for one week."""

    week_start: str
    capacity_hours: float
    assigned_hours: float
    logged_hours: float
    slack_hours: float
    overload: bool


class StaffingAssignmentOut(BaseModel):
    """Plan vs remaining for one assignment overlapping the first week."""

    award_id: int
    short_code: str
    task_id: int | None = None
    task_short_code: str | None = None
    hours_per_week: float
    plan_cents: int | None = None
    remaining_personnel_cents: int | None = None
    remaining_funded_cents: int | None = None
    personnel_fit: bool | None = None
    funded_fit: bool | None = None


class StaffingTaskOut(BaseModel):
    """Assigned vs logged hours on one task for the first week."""

    award_id: int
    short_code: str
    task_id: int | None = None
    task_short_code: str | None = None
    assigned_hours: float
    logged_hours: float


class UtilizationOut(BaseModel):
    """Hours by time_code for the staffing window. Not payroll."""

    person_id: int
    display_name: str
    hours_by_code: dict[str, float]
    direct_hours: float
    total_hours: float
    direct_pct: int | None = None


class StaffingPersonOut(BaseModel):
    """Forward staffing row."""

    person_id: int
    display_name: str
    overload: bool
    weeks: list[StaffingWeekOut] = Field(default_factory=list)
    assignments: list[StaffingAssignmentOut] = Field(default_factory=list)
    tasks: list[StaffingTaskOut] = Field(default_factory=list)


class StaffingOut(BaseModel):
    """Capacity vs plan vs logged (D41)."""

    week_start: str
    weeks: int
    people: list[StaffingPersonOut] = Field(default_factory=list)
    utilization: list[UtilizationOut] = Field(default_factory=list)


class StaffingScenarioIn(BaseModel):
    """What-if hours. Does not persist."""

    person_id: int
    award_id: int
    hours_per_week: float = Field(gt=0)
    week_start: str | None = None
    weeks: int = Field(default=1, ge=1, le=12)


class StaffingScenarioOut(BaseModel):
    """Loaded preview for a hypothetical assignment."""

    person_id: int
    award_id: int
    hours_per_week: float
    weeks: int
    loaded_rate_cents: int | None = None
    plan_cents_per_week: int | None = None
    plan_cents: int | None = None
    remaining_personnel_cents: int | None = None
    remaining_funded_cents: int | None = None
    personnel_fit: bool | None = None
    funded_fit: bool | None = None


class SearchHitOut(BaseModel):
    """One search match. Admin-only; may include money-free labels."""

    kind: str
    id: int
    label: str
    award_id: int | None = None
    href: str


class SearchOut(BaseModel):
    """Grouped search hits."""

    query: str
    hits: list[SearchHitOut] = Field(default_factory=list)


class FundingExpectationIn(BaseModel):
    """Expected increment. Not remaining."""

    expected_date: str
    amount_cents: int = Field(ge=0)
    notes: str | None = None


class FundingExpectationOut(BaseModel):
    """Stored expected increment."""

    funding_expectation_id: int
    award_id: int
    expected_date: str
    amount_cents: int
    notes: str | None
    created_at: str
