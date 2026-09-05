"""My week, approvals, and person base rates."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import display_name_for, get_current_user, get_db, require_admin
from ledger.models import Person, TimesheetLine, TimesheetPeriod, UserAccount
from ledger.schemas.time import (
    PersonRateIn,
    PersonRateOut,
    ReturnWeekIn,
    TimesheetLineAdminOut,
    TimesheetLineOut,
    WeekAdminOut,
    WeekOut,
    WeekPut,
)
from ledger.services.time import (
    TimeError,
    add_person_rate,
    approve_period,
    get_or_create_period,
    hundredths_to_hours,
    period_hours_total,
    preview_labor_line,
    replace_week_lines,
    return_period,
    submit_period,
)

me_router = APIRouter(prefix="/me", tags=["time"])
approvals_router = APIRouter(prefix="/approvals", tags=["time"])
rates_router = APIRouter(tags=["people"])


def _http(exc: TimeError, conflict: bool = False) -> HTTPException:
    code = status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST
    message = str(exc).lower()
    if "already" in message or "exceed" in message:
        code = status.HTTP_409_CONFLICT
    return HTTPException(code, str(exc))


def _employee_week(session: Session, period: TimesheetPeriod) -> WeekOut:
    lines = session.scalars(
        select(TimesheetLine)
        .where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
        .order_by(TimesheetLine.work_date, TimesheetLine.timesheet_line_id)
    ).all()
    return WeekOut(
        timesheet_period_id=period.timesheet_period_id,
        person_id=period.person_id,
        week_start=period.week_start,
        status_code=period.status_code,
        return_comment=period.return_comment,
        hours_total=period_hours_total(session, period),
        lines=[
            TimesheetLineOut(
                timesheet_line_id=line.timesheet_line_id,
                work_date=line.work_date,
                hours=hundredths_to_hours(line.hours_hundredths),
                time_code=line.time_code,
                award_id=line.award_id,
                task_id=line.task_id,
            )
            for line in lines
        ],
    )


def _admin_week(session: Session, period: TimesheetPeriod) -> WeekAdminOut:
    person = session.get(Person, period.person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    lines = session.scalars(
        select(TimesheetLine)
        .where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
        .order_by(TimesheetLine.work_date, TimesheetLine.timesheet_line_id)
    ).all()
    admin_lines: list[TimesheetLineAdminOut] = []
    total_amount = 0
    for line in lines:
        loaded = None
        amount = None
        if line.award_id is not None:
            try:
                preview = preview_labor_line(session, person, line)
                loaded = preview.loaded_rate_cents
                amount = preview.amount_cents
                total_amount += amount
            except TimeError:
                loaded = None
                amount = None
        admin_lines.append(
            TimesheetLineAdminOut(
                timesheet_line_id=line.timesheet_line_id,
                work_date=line.work_date,
                hours=hundredths_to_hours(line.hours_hundredths),
                time_code=line.time_code,
                award_id=line.award_id,
                task_id=line.task_id,
                loaded_rate_cents=loaded,
                amount_cents=amount,
            )
        )
    account = session.scalar(select(UserAccount).where(UserAccount.person_id == person.person_id))
    name = display_name_for(session, account) if account else person.display_name
    return WeekAdminOut(
        timesheet_period_id=period.timesheet_period_id,
        person_id=period.person_id,
        display_name=name,
        week_start=period.week_start,
        status_code=period.status_code,
        return_comment=period.return_comment,
        hours_total=period_hours_total(session, period),
        amount_cents=total_amount,
        lines=admin_lines,
    )


@me_router.get("/week", response_model=WeekOut)
def get_my_week(
    week_start: str | None = None,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> WeekOut:
    """Employee home: hours and awards, no dollars."""
    start = week_start or datetime.now(UTC).date().isoformat()
    period = get_or_create_period(session, user.person_id, start, prefill=True)
    return _employee_week(session, period)


@me_router.put("/week", response_model=WeekOut)
def put_my_week(
    payload: WeekPut,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> WeekOut:
    """Replace the current user's draft/returned week."""
    start = payload.week_start or datetime.now(UTC).date().isoformat()
    period = get_or_create_period(session, user.person_id, start)
    try:
        replace_week_lines(
            session,
            period,
            [line.model_dump() for line in payload.lines],
        )
    except TimeError as exc:
        raise _http(exc) from exc
    return _employee_week(session, period)


@me_router.post("/week/submit", response_model=WeekOut)
def submit_my_week(
    week_start: str | None = None,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> WeekOut:
    """Submit the current user's week to the admin queue."""
    start = week_start or datetime.now(UTC).date().isoformat()
    period = get_or_create_period(session, user.person_id, start)
    try:
        submit_period(session, period, actor_id=user.user_account_id)
    except TimeError as exc:
        raise _http(exc) from exc
    return _employee_week(session, period)


@approvals_router.get("", response_model=list[WeekAdminOut])
def list_approvals(
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[WeekAdminOut]:
    """Submitted weeks waiting on the sole approver."""
    periods = session.scalars(
        select(TimesheetPeriod)
        .where(TimesheetPeriod.status_code == "submitted")
        .order_by(TimesheetPeriod.week_start, TimesheetPeriod.person_id)
    ).all()
    return [_admin_week(session, period) for period in periods]


@approvals_router.get("/{period_id}", response_model=WeekAdminOut)
def get_approval(
    period_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WeekAdminOut:
    """One week with preview dollars."""
    period = session.get(TimesheetPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "timesheet not found")
    if admin.role_code != "admin" and period.person_id != admin.person_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your timesheet")
    return _admin_week(session, period)


@approvals_router.post("/{period_id}/approve", response_model=WeekAdminOut)
def approve_week(
    period_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WeekAdminOut:
    """Post labor charges and mark the week approved."""
    period = session.get(TimesheetPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "timesheet not found")
    try:
        approve_period(session, period, admin)
    except TimeError as exc:
        raise _http(exc) from exc
    return _admin_week(session, period)


@approvals_router.post("/{period_id}/return", response_model=WeekAdminOut)
def bounce_week(
    period_id: int,
    payload: ReturnWeekIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WeekAdminOut:
    """Return a submitted week to draft with a comment."""
    period = session.get(TimesheetPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "timesheet not found")
    try:
        return_period(session, period, payload.comment, actor_id=admin.user_account_id)
    except TimeError as exc:
        raise _http(exc) from exc
    return _admin_week(session, period)


@rates_router.get("/people/{person_id}/rates", response_model=list[PersonRateOut])
def list_rates(
    person_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[PersonRateOut]:
    """Dated base rates for one person."""
    from ledger.models import PersonRate

    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    rows = session.scalars(
        select(PersonRate)
        .where(PersonRate.person_id == person_id)
        .order_by(PersonRate.effective_from)
    ).all()
    return [
        PersonRateOut(
            person_rate_id=row.person_rate_id,
            person_id=row.person_id,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            base_rate_cents=row.base_rate_cents,
            hours_per_year=row.hours_per_year,
        )
        for row in rows
    ]


@rates_router.post(
    "/people/{person_id}/rates",
    response_model=PersonRateOut,
    status_code=status.HTTP_201_CREATED,
)
def post_rate(
    person_id: int,
    payload: PersonRateIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> PersonRateOut:
    """Insert a new dated base rate; close the previous open row."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    try:
        row = add_person_rate(
            session,
            person,
            effective_from=payload.effective_from,
            base_rate_cents=payload.base_rate_cents,
            salary_cents=payload.salary_cents,
            hours_per_year=payload.hours_per_year,
            actor_id=admin.user_account_id,
        )
    except TimeError as exc:
        raise _http(exc) from exc
    return PersonRateOut(
        person_rate_id=row.person_rate_id,
        person_id=row.person_id,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        base_rate_cents=row.base_rate_cents,
        hours_per_year=row.hours_per_year,
    )
