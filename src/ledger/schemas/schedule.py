"""Pydantic payloads for tasks, assignments, and capacity."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """New work package on an award."""

    short_code: str
    title: str
    status_code: str = "open"


class TaskUpdate(BaseModel):
    """Patch title and/or status. Close is a status, not a delete."""

    title: str | None = None
    status_code: str | None = None
    short_code: str | None = None


class TaskCardOut(BaseModel):
    """Employee-visible task. No money (D22)."""

    task_id: int
    award_id: int
    short_code: str
    title: str
    status_code: str


class AssignmentCreate(BaseModel):
    """Planned hours/week for a person on an award (optional task)."""

    person_id: int
    award_id: int
    task_id: int | None = None
    hours_per_week: float = Field(gt=0)
    effective_from: str
    effective_to: str | None = None


class AssignmentOut(BaseModel):
    """Stored assignment. Hours, not dollars."""

    assignment_id: int
    person_id: int
    award_id: int
    task_id: int | None
    hours_per_week: float
    effective_from: str
    effective_to: str | None


class CapacityIn(BaseModel):
    """New dated available hours/week. Zero is allowed (D24)."""

    effective_from: str
    hours_per_week: float = Field(ge=0)


class CapacityOut(BaseModel):
    """Stored capacity row."""

    person_capacity_id: int
    person_id: int
    hours_per_week: float
    effective_from: str
    effective_to: str | None


class CapacityWeekRow(BaseModel):
    """Admin planned-vs-capacity hours for one person and week."""

    person_id: int
    display_name: str
    capacity_hours: float
    planned_hours: float
    over_capacity: bool
