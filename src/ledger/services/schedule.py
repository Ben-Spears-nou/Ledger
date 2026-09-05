"""Tasks, dated assignments, and person capacity (Phase 3)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from ledger.models import (
    Assignment,
    Award,
    Person,
    PersonCapacity,
    Task,
    TimesheetLine,
    UserAccount,
)
from ledger.schemas.schedule import (
    AssignmentCreate,
    AssignmentOut,
    CapacityIn,
    CapacityOut,
    CapacityWeekRow,
    TaskCardOut,
    TaskCreate,
    TaskUpdate,
)
from ledger.services.audit import record_event
from ledger.services.time import (
    hundredths_to_hours,
    week_start_on_or_before,
)


class ScheduleError(ValueError):
    """Domain error turned into HTTP 400 by the API."""


def hours_per_week_to_hundredths(hours: float, *, allow_zero: bool = False) -> int:
    """Convert weekly hours to integer hundredths."""
    hundredths = round(hours * 100)
    if hundredths < 0:
        raise ScheduleError("hours cannot be negative")
    if hundredths == 0 and not allow_zero:
        raise ScheduleError("hours must be greater than zero")
    return hundredths


def serialize_task(task: Task) -> TaskCardOut:
    """Slim task DTO — no money (D22)."""
    return TaskCardOut(
        task_id=task.task_id,
        award_id=task.award_id,
        short_code=task.short_code,
        title=task.title,
        status_code=task.status_code,
    )


def serialize_assignment(row: Assignment) -> AssignmentOut:
    """Hours-only assignment payload."""
    return AssignmentOut(
        assignment_id=row.assignment_id,
        person_id=row.person_id,
        award_id=row.award_id,
        task_id=row.task_id,
        hours_per_week=hundredths_to_hours(row.hours_hundredths_per_week),
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )


def serialize_capacity(row: PersonCapacity) -> CapacityOut:
    """Hours-only capacity payload."""
    return CapacityOut(
        person_capacity_id=row.person_capacity_id,
        person_id=row.person_id,
        hours_per_week=hundredths_to_hours(row.hours_hundredths_per_week),
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )


def _require_award(session: Session, award_id: int) -> Award:
    award = session.get(Award, award_id)
    if award is None:
        raise ScheduleError("award not found")
    return award


def _require_person(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise ScheduleError("person not found")
    return person


def _require_task(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise ScheduleError("task not found")
    return task


def list_tasks(session: Session, award_id: int | None = None) -> list[Task]:
    """Tasks, optionally filtered to one award. Newest id last."""
    stmt: Select[tuple[Task]] = select(Task).order_by(Task.award_id, Task.short_code)
    if award_id is not None:
        stmt = stmt.where(Task.award_id == award_id)
    return list(session.scalars(stmt))


def create_task(
    session: Session, award: Award, payload: TaskCreate, *, actor_id: int | None
) -> Task:
    """Insert a task on an award."""
    if award.status_code == "closed":
        raise ScheduleError("cannot add a task to a closed award")
    status = (payload.status_code or "open").strip()
    if status not in {"open", "closed"}:
        raise ScheduleError("status_code must be open or closed")
    short = payload.short_code.strip()
    title = payload.title.strip()
    if not short or not title:
        raise ScheduleError("short_code and title are required")
    existing = session.scalar(
        select(Task).where(Task.award_id == award.award_id, Task.short_code == short)
    )
    if existing is not None:
        raise ScheduleError("task short_code already exists on this award")
    task = Task(
        award_id=award.award_id,
        short_code=short,
        title=title,
        status_code=status,
        created_by=actor_id,
    )
    session.add(task)
    session.flush()
    record_event(
        session,
        action="task_create",
        entity_type="task",
        entity_id=task.task_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id, "short_code": short},
    )
    return task


def update_task(session: Session, task: Task, payload: TaskUpdate) -> Task:
    """Patch a task. Close is a status, not a delete."""
    if payload.status_code is not None:
        status = payload.status_code.strip()
        if status not in {"open", "closed"}:
            raise ScheduleError("status_code must be open or closed")
        task.status_code = status
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise ScheduleError("title is required")
        task.title = title
    if payload.short_code is not None:
        short = payload.short_code.strip()
        if not short:
            raise ScheduleError("short_code is required")
        clash = session.scalar(
            select(Task).where(
                Task.award_id == task.award_id,
                Task.short_code == short,
                Task.task_id != task.task_id,
            )
        )
        if clash is not None:
            raise ScheduleError("task short_code already exists on this award")
        task.short_code = short
    session.flush()
    return task


def close_open_assignments(
    session: Session,
    person_id: int,
    award_id: int,
    task_id: int | None,
    new_from: str,
) -> None:
    """Close the open assignment for this person + award + task (D5)."""
    stmt = select(Assignment).where(
        Assignment.person_id == person_id,
        Assignment.award_id == award_id,
        Assignment.effective_to.is_(None),
    )
    if task_id is None:
        stmt = stmt.where(Assignment.task_id.is_(None))
    else:
        stmt = stmt.where(Assignment.task_id == task_id)
    parsed = date.fromisoformat(new_from)
    closed_on = (parsed - timedelta(days=1)).isoformat()
    for row in session.scalars(stmt):
        row.effective_to = closed_on if closed_on >= row.effective_from else new_from


def create_assignment(
    session: Session, payload: AssignmentCreate, *, actor_id: int | None
) -> Assignment:
    """Insert a dated assignment; close the previous open row for the same key."""
    _require_person(session, payload.person_id)
    award = _require_award(session, payload.award_id)
    if award.status_code == "closed":
        raise ScheduleError("cannot assign to a closed award")
    task_id = payload.task_id
    if task_id is not None:
        task = _require_task(session, task_id)
        if task.award_id != award.award_id:
            raise ScheduleError("task does not belong to this award")
        if task.status_code == "closed":
            raise ScheduleError("cannot assign to a closed task")
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise ScheduleError("effective_to must be on or after effective_from")
    hundredths = hours_per_week_to_hundredths(payload.hours_per_week)
    close_open_assignments(
        session, payload.person_id, payload.award_id, task_id, payload.effective_from
    )
    row = Assignment(
        person_id=payload.person_id,
        award_id=payload.award_id,
        task_id=task_id,
        hours_hundredths_per_week=hundredths,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="assignment_create",
        entity_type="assignment",
        entity_id=row.assignment_id,
        actor_user_id=actor_id,
        detail={
            "person_id": payload.person_id,
            "award_id": payload.award_id,
            "task_id": task_id,
        },
    )
    return row


def list_assignments(
    session: Session,
    *,
    person_id: int | None = None,
    award_id: int | None = None,
) -> list[Assignment]:
    """Assignments, newest effective_from last."""
    stmt = select(Assignment).order_by(
        Assignment.person_id, Assignment.award_id, Assignment.effective_from
    )
    if person_id is not None:
        stmt = stmt.where(Assignment.person_id == person_id)
    if award_id is not None:
        stmt = stmt.where(Assignment.award_id == award_id)
    return list(session.scalars(stmt))


def overlapping_assignments(session: Session, person_id: int, week_start: str) -> list[Assignment]:
    """Assignments that overlap the calendar week starting Monday ``week_start``."""
    monday = week_start_on_or_before(week_start)
    week_end = (date.fromisoformat(monday) + timedelta(days=6)).isoformat()
    rows = session.scalars(
        select(Assignment)
        .where(
            Assignment.person_id == person_id,
            Assignment.effective_from <= week_end,
            or_(Assignment.effective_to.is_(None), Assignment.effective_to >= monday),
        )
        .order_by(Assignment.award_id, Assignment.assignment_id)
    ).all()
    usable: list[Assignment] = []
    for row in rows:
        award = session.get(Award, row.award_id)
        if award is None or award.status_code == "closed":
            continue
        if row.task_id is not None:
            task = session.get(Task, row.task_id)
            if task is None or task.status_code == "closed":
                continue
        usable.append(row)
    return usable


def prefill_period_from_assignments(session: Session, period) -> None:
    """Copy overlapping assignments onto a newly created empty draft (D7, D23)."""
    from ledger.models import TimesheetPeriod

    if not isinstance(period, TimesheetPeriod):
        return
    if period.status_code != "draft":
        return
    existing = session.scalars(
        select(TimesheetLine).where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
    ).first()
    if existing is not None:
        return
    for row in overlapping_assignments(session, period.person_id, period.week_start):
        session.add(
            TimesheetLine(
                timesheet_period_id=period.timesheet_period_id,
                work_date=period.week_start,
                hours_hundredths=row.hours_hundredths_per_week,
                time_code="award",
                award_id=row.award_id,
                task_id=row.task_id,
            )
        )
    session.flush()


def close_open_capacity(session: Session, person_id: int, new_from: str) -> None:
    """Close the open capacity row. Does not overwrite history (D5)."""
    open_rows = session.scalars(
        select(PersonCapacity).where(
            PersonCapacity.person_id == person_id,
            PersonCapacity.effective_to.is_(None),
        )
    ).all()
    parsed = date.fromisoformat(new_from)
    closed_on = (parsed - timedelta(days=1)).isoformat()
    for row in open_rows:
        row.effective_to = closed_on if closed_on >= row.effective_from else new_from


def add_person_capacity(
    session: Session,
    person: Person,
    payload: CapacityIn,
    *,
    actor_id: int | None,
) -> PersonCapacity:
    """Insert a dated capacity row."""
    hundredths = hours_per_week_to_hundredths(payload.hours_per_week, allow_zero=True)
    close_open_capacity(session, person.person_id, payload.effective_from)
    row = PersonCapacity(
        person_id=person.person_id,
        hours_hundredths_per_week=hundredths,
        effective_from=payload.effective_from,
        effective_to=None,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="capacity_create",
        entity_type="person_capacity",
        entity_id=row.person_capacity_id,
        actor_user_id=actor_id,
        detail={"person_id": person.person_id, "effective_from": payload.effective_from},
    )
    return row


def list_capacity(session: Session, person_id: int) -> list[PersonCapacity]:
    """Dated capacity rows for one person."""
    return list(
        session.scalars(
            select(PersonCapacity)
            .where(PersonCapacity.person_id == person_id)
            .order_by(PersonCapacity.effective_from)
        )
    )


def _as_of_capacity(session: Session, person_id: int, as_of: str) -> PersonCapacity | None:
    return session.scalar(
        select(PersonCapacity)
        .where(
            PersonCapacity.person_id == person_id,
            PersonCapacity.effective_from <= as_of,
            or_(PersonCapacity.effective_to.is_(None), PersonCapacity.effective_to >= as_of),
        )
        .order_by(PersonCapacity.effective_from.desc())
    )


def capacity_for_week(session: Session, week_start: str) -> list[CapacityWeekRow]:
    """Planned vs capacity hours for every person with a login."""
    monday = week_start_on_or_before(week_start)
    accounts = session.scalars(select(UserAccount).order_by(UserAccount.person_id)).all()
    result: list[CapacityWeekRow] = []
    seen: set[int] = set()
    for account in accounts:
        if account.person_id in seen:
            continue
        seen.add(account.person_id)
        person = session.get(Person, account.person_id)
        if person is None:
            continue
        cap = _as_of_capacity(session, person.person_id, monday)
        capacity_hours = hundredths_to_hours(cap.hours_hundredths_per_week) if cap else 0.0
        planned_hundredths = sum(
            row.hours_hundredths_per_week
            for row in overlapping_assignments(session, person.person_id, monday)
        )
        planned_hours = hundredths_to_hours(planned_hundredths)
        result.append(
            CapacityWeekRow(
                person_id=person.person_id,
                display_name=person.display_name,
                capacity_hours=capacity_hours,
                planned_hours=planned_hours,
                over_capacity=planned_hours > capacity_hours,
            )
        )
    return result
