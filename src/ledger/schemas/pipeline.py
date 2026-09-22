"""Pydantic payloads for pipeline nodes, burn, and alerts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineCreate(BaseModel):
    """New forecast row on an award."""

    kind_code: str
    title: str
    amount_cents: int = Field(ge=0)
    expected_date: str | None = None
    notes: str | None = None


class PipelinePatch(BaseModel):
    """Edit forecast. Unset fields stay."""

    kind_code: str | None = None
    title: str | None = None
    amount_cents: int | None = Field(default=None, ge=0)
    expected_date: str | None = None
    notes: str | None = None


class PipelineOut(BaseModel):
    """Admin pipeline node, including award identity for the list."""

    pipeline_node_id: int
    award_id: int
    award_short_code: str | None = None
    kind_code: str
    title: str
    amount_cents: int
    expected_date: str | None
    notes: str | None
    created_at: str


class BurnMonthOut(BaseModel):
    """One calendar month of posted actuals."""

    year_month: str
    actual_cents: int


class ForecastMonthOut(BaseModel):
    """One month on the integrated burn and runway forecast."""

    year_month: str
    actual_cents: int = 0
    cumulative_actual_cents: int = 0
    planned_cents: int | None = None
    commitment_cents: int = 0
    funding_expected_cents: int = 0
    projected_cumulative_cents: int = 0


class BurnWindowOut(BaseModel):
    """Burn rate computed over one trailing calendar-day window."""

    days: int
    window_start: str
    window_end: str
    actual_cents: int
    daily_burn_cents: int
    monthly_rate_cents: int


class AwardBurnOut(BaseModel):
    """Monthly burn plus integer EAC and runway (D33)."""

    award_id: int
    award_short_code: str
    award_title: str
    status_code: str
    pop_end: str
    as_of: str
    actual_cents: int
    remaining_approved_cents: int
    window_start: str
    window_end: str
    window_actual_cents: int
    window_days: int
    selected_window_days: int
    daily_burn_cents: int
    days_to_pop_end: int
    eac_cents: int
    runway_days: int | None
    approved_ceiling_cents: int
    funded_ceiling_cents: int
    committed_cents: int
    runway_end: str | None = None
    windows: list[BurnWindowOut] = Field(default_factory=list)
    months: list[BurnMonthOut] = Field(default_factory=list)
    forecast_months: list[ForecastMonthOut] = Field(default_factory=list)


class AlertOut(BaseModel):
    """Computed 75% or PoP warning (D34). Not stored."""

    alert_code: str
    award_id: int
    award_short_code: str
    as_of: str
    actual_cents: int | None = None
    basis_cents: int | None = None
    ceiling_warn_pct: int | None = None
    pop_end: str | None = None
    days_to_pop_end: int | None = None
