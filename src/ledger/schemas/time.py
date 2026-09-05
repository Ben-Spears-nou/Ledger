"""Pydantic payloads for timesheets and person rates."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersonRateIn(BaseModel):
    """New dated base rate. Salary + hours/year derives hourly cents."""

    effective_from: str
    base_rate_cents: int | None = Field(default=None, ge=0)
    salary_cents: int | None = Field(default=None, ge=0)
    hours_per_year: int | None = Field(default=None, gt=0)


class PersonRateOut(BaseModel):
    """Stored base-rate row."""

    person_rate_id: int
    person_id: int
    effective_from: str
    effective_to: str | None
    base_rate_cents: int
    hours_per_year: int | None


class TimesheetLineIn(BaseModel):
    """One day of hours. Employees send hours and award/time_code only.

    Extra fields are ignored so later phases can add line fields without a
    My week redesign.
    """

    model_config = ConfigDict(extra="ignore")

    work_date: str
    hours: float = Field(gt=0)
    award_id: int | None = None
    time_code: str | None = None
    task_id: int | None = None


class WeekPut(BaseModel):
    """Replace the current user's draft week."""

    week_start: str | None = None
    lines: list[TimesheetLineIn] = Field(default_factory=list)


class TimesheetLineOut(BaseModel):
    """Employee-visible line: hours, not dollars."""

    timesheet_line_id: int
    work_date: str
    hours: float
    time_code: str
    award_id: int | None
    task_id: int | None = None


class TimesheetLineAdminOut(TimesheetLineOut):
    """Admin preview includes loaded rate and line $."""

    loaded_rate_cents: int | None = None
    amount_cents: int | None = None


class WeekOut(BaseModel):
    """Employee My week payload (no dollars)."""

    timesheet_period_id: int
    person_id: int
    week_start: str
    status_code: str
    return_comment: str | None
    hours_total: float
    lines: list[TimesheetLineOut]


class WeekAdminOut(BaseModel):
    """Approver view with preview dollars."""

    timesheet_period_id: int
    person_id: int
    display_name: str
    week_start: str
    status_code: str
    return_comment: str | None
    hours_total: float
    amount_cents: int
    lines: list[TimesheetLineAdminOut]


class ReturnWeekIn(BaseModel):
    """Comment when bouncing a submitted week."""

    comment: str
