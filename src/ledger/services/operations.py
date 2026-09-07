"""Home, staffing, search, and close — computed, not remaining (D40–D44)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ledger.models import (
    Award,
    Clin,
    Commitment,
    ComplianceItem,
    Document,
    FundingExpectation,
    Person,
    Task,
    TimesheetLine,
    TimesheetPeriod,
    UserAccount,
)
from ledger.rates import loaded_rate_cents
from ledger.schemas.operations import (
    CloseChecklistOut,
    FundingExpectationIn,
    FundingExpectationOut,
    HomeApprovalOut,
    HomeCommitmentOut,
    HomeComplianceOut,
    HomeOut,
    MissingWeekOut,
    PlannedHoursOut,
    PortfolioRowOut,
    SearchHitOut,
    SearchOut,
    StaffingAssignmentOut,
    StaffingOut,
    StaffingPersonOut,
    StaffingScenarioIn,
    StaffingScenarioOut,
    StaffingTaskOut,
    StaffingWeekOut,
    UtilizationOut,
)
from ledger.services.audit import record_event
from ledger.services.awards import line_remaining_map, remaining_for
from ledger.services.burn import award_burn, list_alerts
from ledger.services.schedule import (
    as_of_capacity,
    overlapping_assignments,
)
from ledger.services.time import (
    amount_cents_for,
    as_of_policy,
    as_of_rate,
    hundredths_to_hours,
    override_for,
    period_hours_total,
    week_start_on_or_before,
)

COMPLIANCE_WINDOW_DAYS = 14
AGING_DAYS = 14
MAX_STAFFING_WEEKS = 12
SEARCH_LIMIT = 20


class OperationsError(ValueError):
    """Domain error turned into HTTP 400 by the API."""


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise OperationsError(f"{field} must be YYYY-MM-DD") from exc


def _as_of(value: str | None) -> date:
    if value:
        return date.fromisoformat(_iso_date(value, field="as_of"))
    return datetime.now(UTC).date()


def _mondays(start: str, weeks: int) -> list[str]:
    monday = date.fromisoformat(week_start_on_or_before(start))
    return [(monday + timedelta(days=7 * index)).isoformat() for index in range(weeks)]


def _active_people(session: Session, as_of: str) -> list[tuple[Person, UserAccount]]:
    rows: list[tuple[Person, UserAccount]] = []
    for account in session.scalars(select(UserAccount).order_by(UserAccount.person_id)):
        if not account.is_active:
            continue
        person = session.get(Person, account.person_id)
        if person is None:
            continue
        if person.term_date and person.term_date < as_of:
            continue
        if person.hire_date and person.hire_date > as_of:
            continue
        rows.append((person, account))
    return rows


def _period_for(session: Session, person_id: int, week_start: str) -> TimesheetPeriod | None:
    return session.scalar(
        select(TimesheetPeriod).where(
            TimesheetPeriod.person_id == person_id,
            TimesheetPeriod.week_start == week_start,
        )
    )


def _logged_hundredths(
    session: Session, person_id: int, week_start: str, *, award_id: int | None = None
) -> int:
    period = _period_for(session, person_id, week_start)
    if period is None:
        return 0
    stmt = select(func.coalesce(func.sum(TimesheetLine.hours_hundredths), 0)).where(
        TimesheetLine.timesheet_period_id == period.timesheet_period_id
    )
    if award_id is not None:
        stmt = stmt.where(TimesheetLine.award_id == award_id)
    return int(session.scalar(stmt) or 0)


def _logged_by_code(session: Session, person_id: int, week_starts: list[str]) -> dict[str, int]:
    totals: dict[str, int] = {}
    periods = session.scalars(
        select(TimesheetPeriod).where(
            TimesheetPeriod.person_id == person_id,
            TimesheetPeriod.week_start.in_(week_starts),
        )
    ).all()
    if not periods:
        return totals
    ids = [row.timesheet_period_id for row in periods]
    rows = session.execute(
        select(TimesheetLine.time_code, func.coalesce(func.sum(TimesheetLine.hours_hundredths), 0))
        .where(TimesheetLine.timesheet_period_id.in_(ids))
        .group_by(TimesheetLine.time_code)
    ).all()
    for code, hundredths in rows:
        totals[str(code)] = int(hundredths)
    return totals


def _personnel_remaining_cents(session: Session, award: Award) -> int | None:
    remaining = remaining_for(session, award.award_id)
    if remaining is None:
        return None
    policy = as_of_policy(session, award.award_id, datetime.now(UTC).date().isoformat())
    if policy is None or policy.labor_budget_line_id is None:
        return remaining.remaining_approved_cents
    money = line_remaining_map(session, award.award_id)
    actual, committed, left = money.get(policy.labor_budget_line_id, (0, 0, 0))
    del actual, committed
    return left


def plan_cents_for(
    session: Session, person: Person, award: Award, hours_hundredths: int, as_of: str
) -> tuple[int | None, int | None]:
    """Return (loaded_rate_cents, plan_cents) or Nones if rates are missing."""
    person_rate = as_of_rate(session, person.person_id, as_of)
    policy = as_of_policy(session, award.award_id, as_of)
    if person_rate is None or policy is None:
        return None, None
    override = override_for(session, policy, person)
    override_cents = override.loaded_rate_cents if override else None
    try:
        loaded = loaded_rate_cents(person_rate.base_rate_cents, policy, override_cents)
    except ValueError:
        return None, None
    return loaded, amount_cents_for(hours_hundredths, loaded)


def planned_hours_for_week(
    session: Session, person_id: int, week_start: str
) -> list[PlannedHoursOut]:
    """Employee-visible assignment hours. No dollars."""
    monday = week_start_on_or_before(week_start)
    return [
        PlannedHoursOut(
            award_id=row.award_id,
            task_id=row.task_id,
            hours_per_week=hundredths_to_hours(row.hours_hundredths_per_week),
        )
        for row in overlapping_assignments(session, person_id, monday)
    ]


def serialize_funding(row) -> FundingExpectationOut:
    """Funding expectation DTO."""
    return FundingExpectationOut(
        funding_expectation_id=row.funding_expectation_id,
        award_id=row.award_id,
        expected_date=row.expected_date,
        amount_cents=row.amount_cents,
        notes=row.notes,
        created_at=row.created_at,
    )


def list_funding_expectations(session: Session, award_id: int) -> list[FundingExpectationOut]:
    """Expected increments on one award."""
    rows = session.scalars(
        select(FundingExpectation)
        .where(FundingExpectation.award_id == award_id)
        .order_by(FundingExpectation.expected_date, FundingExpectation.funding_expectation_id)
    ).all()
    return [serialize_funding(row) for row in rows]


def add_funding_expectation(
    session: Session, award: Award, payload: FundingExpectationIn, *, actor_id: int | None
):
    """Insert an expected increment. Does not change remaining."""
    when = _iso_date(payload.expected_date, field="expected_date")
    row = FundingExpectation(
        award_id=award.award_id,
        expected_date=when,
        amount_cents=payload.amount_cents,
        notes=payload.notes,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="funding_expectation_create",
        entity_type="funding_expectation",
        entity_id=row.funding_expectation_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id, "amount_cents": row.amount_cents},
    )
    return row


def delete_funding_expectation(session: Session, row, *, actor_id: int | None) -> None:
    """Remove an expected increment."""
    expectation_id = row.funding_expectation_id
    award_id = row.award_id
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="funding_expectation_delete",
        entity_type="funding_expectation",
        entity_id=expectation_id,
        actor_user_id=actor_id,
        detail={"award_id": award_id},
    )


def home_board(session: Session, *, as_of: str | None) -> HomeOut:
    """Build the admin operations board."""
    as_of_date = _as_of(as_of)
    as_of_iso = as_of_date.isoformat()
    monday = week_start_on_or_before(as_of_iso)
    due_until = (as_of_date + timedelta(days=COMPLIANCE_WINDOW_DAYS)).isoformat()
    aging_on = (as_of_date - timedelta(days=AGING_DAYS)).isoformat()

    missing: list[MissingWeekOut] = []
    for person, account in _active_people(session, as_of_iso):
        period = _period_for(session, person.person_id, monday)
        status = period.status_code if period else None
        if status in {"submitted", "approved"}:
            continue
        missing.append(
            MissingWeekOut(
                person_id=person.person_id,
                display_name=person.display_name,
                username=account.username,
                status_code=status,
            )
        )

    approvals: list[HomeApprovalOut] = []
    submitted = session.scalars(
        select(TimesheetPeriod)
        .where(TimesheetPeriod.status_code == "submitted")
        .order_by(TimesheetPeriod.week_start, TimesheetPeriod.person_id)
    ).all()
    for period in submitted:
        person = session.get(Person, period.person_id)
        approvals.append(
            HomeApprovalOut(
                timesheet_period_id=period.timesheet_period_id,
                person_id=period.person_id,
                display_name=person.display_name if person else str(period.person_id),
                week_start=period.week_start,
                hours_total=period_hours_total(session, period),
            )
        )

    compliance_due: list[HomeComplianceOut] = []
    items = session.scalars(
        select(ComplianceItem)
        .where(ComplianceItem.status_code == "open", ComplianceItem.due_date <= due_until)
        .order_by(ComplianceItem.due_date)
    ).all()
    for item in items:
        award = session.get(Award, item.award_id)
        compliance_due.append(
            HomeComplianceOut(
                compliance_item_id=item.compliance_item_id,
                award_id=item.award_id,
                award_short_code=award.short_code if award else "",
                title=item.title,
                due_date=item.due_date,
                status_code=item.status_code,
                document_id=item.document_id,
            )
        )

    aging: list[HomeCommitmentOut] = []
    opens = session.scalars(select(Commitment).where(Commitment.status_code == "open")).all()
    for row in opens:
        aging_date = row.expected_date or row.effective_date
        if aging_date > aging_on:
            continue
        award = session.get(Award, row.award_id)
        age = (as_of_date - date.fromisoformat(aging_date)).days
        aging.append(
            HomeCommitmentOut(
                commitment_id=row.commitment_id,
                award_id=row.award_id,
                award_short_code=award.short_code if award else "",
                description=row.description,
                amount_cents=row.amount_cents,
                aging_date=aging_date,
                age_days=age,
            )
        )
    aging.sort(key=lambda item: item.aging_date)

    draft_count = int(
        session.scalar(
            select(func.count())
            .select_from(TimesheetPeriod)
            .where(TimesheetPeriod.status_code == "draft")
        )
        or 0
    )
    submitted_count = len(approvals)
    open_commitment_count = int(
        session.scalar(
            select(func.count()).select_from(Commitment).where(Commitment.status_code == "open")
        )
        or 0
    )
    close = CloseChecklistOut(
        as_of=as_of_iso,
        week_start=monday,
        missing_week_count=len(missing),
        draft_count=draft_count,
        submitted_count=submitted_count,
        open_commitment_count=open_commitment_count,
    )

    alert_rows = list_alerts(session, as_of=as_of_iso)
    alerts_by_award: dict[int, list[str]] = {}
    for row in alert_rows:
        alerts_by_award.setdefault(row.award_id, []).append(row.alert_code)

    portfolio: list[PortfolioRowOut] = []
    awards = session.scalars(select(Award).order_by(Award.short_code)).all()
    for award in awards:
        remaining = remaining_for(session, award.award_id)
        burn = award_burn(session, award, as_of=as_of_iso)
        next_item = session.scalar(
            select(ComplianceItem)
            .where(
                ComplianceItem.award_id == award.award_id,
                ComplianceItem.status_code == "open",
            )
            .order_by(ComplianceItem.due_date)
        )
        portfolio.append(
            PortfolioRowOut(
                award_id=award.award_id,
                short_code=award.short_code,
                title=award.title,
                status_code=award.status_code,
                type_code=award.type_code,
                remaining_approved_cents=(remaining.remaining_approved_cents if remaining else 0),
                remaining_funded_cents=remaining.remaining_funded_cents if remaining else 0,
                runway_days=burn.runway_days if burn else None,
                alert_codes=alerts_by_award.get(award.award_id, []),
                next_compliance_due=next_item.due_date if next_item else None,
                next_compliance_title=next_item.title if next_item else None,
                overrun_policy=award.overrun_policy,
            )
        )

    return HomeOut(
        as_of=as_of_iso,
        week_start=monday,
        missing_weeks=missing,
        approvals=approvals,
        compliance_due=compliance_due,
        aging_commitments=aging,
        close=close,
        portfolio=portfolio,
    )


def staffing_board(session: Session, *, week_start: str | None, weeks: int) -> StaffingOut:
    """Capacity vs assigned vs logged for a forward window."""
    if weeks < 1 or weeks > MAX_STAFFING_WEEKS:
        raise OperationsError(f"weeks must be 1–{MAX_STAFFING_WEEKS}")
    monday = week_start_on_or_before(week_start or datetime.now(UTC).date().isoformat())
    window = _mondays(monday, weeks)
    people_out: list[StaffingPersonOut] = []
    utilization: list[UtilizationOut] = []

    for person, _account in _active_people(session, monday):
        week_rows: list[StaffingWeekOut] = []
        any_overload = False
        for week in window:
            cap = as_of_capacity(session, person.person_id, week)
            capacity_h = hundredths_to_hours(cap.hours_hundredths_per_week) if cap else 0.0
            assigned_h = hundredths_to_hours(
                sum(
                    row.hours_hundredths_per_week
                    for row in overlapping_assignments(session, person.person_id, week)
                )
            )
            logged_h = hundredths_to_hours(_logged_hundredths(session, person.person_id, week))
            slack = round(capacity_h - assigned_h, 2)
            overload = assigned_h > capacity_h + 0.001 and capacity_h > 0
            if assigned_h > capacity_h + 0.001 and capacity_h == 0 and assigned_h > 0:
                overload = True
            any_overload = any_overload or overload
            week_rows.append(
                StaffingWeekOut(
                    week_start=week,
                    capacity_hours=capacity_h,
                    assigned_hours=assigned_h,
                    logged_hours=logged_h,
                    slack_hours=slack,
                    overload=overload,
                )
            )

        assignment_out: list[StaffingAssignmentOut] = []
        for row in overlapping_assignments(session, person.person_id, monday):
            award = session.get(Award, row.award_id)
            if award is None:
                continue
            task = session.get(Task, row.task_id) if row.task_id else None
            loaded, plan = plan_cents_for(
                session, person, award, row.hours_hundredths_per_week, monday
            )
            del loaded
            personnel = _personnel_remaining_cents(session, award)
            remaining = remaining_for(session, award.award_id)
            funded = remaining.remaining_funded_cents if remaining else None
            assignment_out.append(
                StaffingAssignmentOut(
                    award_id=award.award_id,
                    short_code=award.short_code,
                    task_id=row.task_id,
                    task_short_code=task.short_code if task else None,
                    hours_per_week=hundredths_to_hours(row.hours_hundredths_per_week),
                    plan_cents=plan,
                    remaining_personnel_cents=personnel,
                    remaining_funded_cents=funded,
                    personnel_fit=None if plan is None or personnel is None else plan <= personnel,
                    funded_fit=None if plan is None or funded is None else plan <= funded,
                )
            )

        task_hours: dict[tuple[int, int | None], list[int]] = {}
        for row in overlapping_assignments(session, person.person_id, monday):
            key = (row.award_id, row.task_id)
            assigned, logged = task_hours.get(key, [0, 0])
            assigned += row.hours_hundredths_per_week
            task_hours[key] = [assigned, logged]
        period = _period_for(session, person.person_id, monday)
        if period is not None:
            for line in session.scalars(
                select(TimesheetLine).where(
                    TimesheetLine.timesheet_period_id == period.timesheet_period_id,
                    TimesheetLine.award_id.is_not(None),
                )
            ):
                key = (int(line.award_id), line.task_id)
                assigned, logged = task_hours.get(key, [0, 0])
                logged += line.hours_hundredths
                task_hours[key] = [assigned, logged]
        tasks_out: list[StaffingTaskOut] = []
        for (award_id, task_id), (assigned, logged) in sorted(task_hours.items()):
            award = session.get(Award, award_id)
            task = session.get(Task, task_id) if task_id else None
            tasks_out.append(
                StaffingTaskOut(
                    award_id=award_id,
                    short_code=award.short_code if award else "",
                    task_id=task_id,
                    task_short_code=task.short_code if task else None,
                    assigned_hours=hundredths_to_hours(assigned),
                    logged_hours=hundredths_to_hours(logged),
                )
            )

        people_out.append(
            StaffingPersonOut(
                person_id=person.person_id,
                display_name=person.display_name,
                overload=any_overload,
                weeks=week_rows,
                assignments=assignment_out,
                tasks=tasks_out,
            )
        )

        by_code = _logged_by_code(session, person.person_id, window)
        hours_by_code = {
            code: hundredths_to_hours(value) for code, value in sorted(by_code.items())
        }
        direct = hundredths_to_hours(by_code.get("award", 0))
        total = hundredths_to_hours(sum(by_code.values()))
        utilization.append(
            UtilizationOut(
                person_id=person.person_id,
                display_name=person.display_name,
                hours_by_code=hours_by_code,
                direct_hours=direct,
                total_hours=total,
                direct_pct=round(direct * 100 / total) if total else None,
            )
        )

    return StaffingOut(week_start=monday, weeks=weeks, people=people_out, utilization=utilization)


def staffing_scenario(session: Session, payload: StaffingScenarioIn) -> StaffingScenarioOut:
    """Preview loaded cost of hypothetical hours. Does not write."""
    weeks = payload.weeks
    if weeks < 1 or weeks > MAX_STAFFING_WEEKS:
        raise OperationsError(f"weeks must be 1–{MAX_STAFFING_WEEKS}")
    monday = week_start_on_or_before(payload.week_start or datetime.now(UTC).date().isoformat())
    person = session.get(Person, payload.person_id)
    award = session.get(Award, payload.award_id)
    if person is None:
        raise OperationsError("person not found")
    if award is None:
        raise OperationsError("award not found")
    from ledger.services.schedule import hours_per_week_to_hundredths

    hundredths = hours_per_week_to_hundredths(payload.hours_per_week)
    loaded, per_week = plan_cents_for(session, person, award, hundredths, monday)
    total = None if per_week is None else per_week * weeks
    personnel = _personnel_remaining_cents(session, award)
    remaining = remaining_for(session, award.award_id)
    funded = remaining.remaining_funded_cents if remaining else None
    return StaffingScenarioOut(
        person_id=person.person_id,
        award_id=award.award_id,
        hours_per_week=payload.hours_per_week,
        weeks=weeks,
        loaded_rate_cents=loaded,
        plan_cents_per_week=per_week,
        plan_cents=total,
        remaining_personnel_cents=personnel,
        remaining_funded_cents=funded,
        personnel_fit=None if total is None or personnel is None else total <= personnel,
        funded_fit=None if total is None or funded is None else total <= funded,
    )


def search_ledger(session: Session, query: str) -> SearchOut:
    """Admin search across awards, people, CLINs, and documents."""
    needle = query.strip()
    if len(needle) < 1:
        raise OperationsError("q is required")
    pattern = f"%{needle.lower()}%"
    hits: list[SearchHitOut] = []

    awards = session.scalars(
        select(Award)
        .where(
            or_(
                func.lower(Award.short_code).like(pattern),
                func.lower(Award.title).like(pattern),
            )
        )
        .order_by(Award.short_code)
        .limit(SEARCH_LIMIT)
    ).all()
    for award in awards:
        hits.append(
            SearchHitOut(
                kind="award",
                id=award.award_id,
                label=f"{award.short_code} · {award.title}",
                award_id=award.award_id,
                href=f"/awards/{award.award_id}",
            )
        )

    people = session.scalars(
        select(Person)
        .where(func.lower(Person.display_name).like(pattern))
        .order_by(Person.display_name)
        .limit(SEARCH_LIMIT)
    ).all()
    accounts = {
        row.person_id: row
        for row in session.scalars(select(UserAccount)).all()
        if row.username and needle.lower() in row.username.lower()
    }
    seen_people = {person.person_id for person in people}
    for account in accounts.values():
        if account.person_id in seen_people:
            continue
        person = session.get(Person, account.person_id)
        if person is not None:
            people.append(person)
    for person in people[:SEARCH_LIMIT]:
        account = session.scalar(
            select(UserAccount).where(UserAccount.person_id == person.person_id)
        )
        label = person.display_name
        if account:
            label = f"{person.display_name} ({account.username})"
        hits.append(
            SearchHitOut(
                kind="person",
                id=person.person_id,
                label=label,
                href="/people",
            )
        )

    clins = session.scalars(
        select(Clin).where(func.lower(Clin.clin_number).like(pattern)).limit(SEARCH_LIMIT)
    ).all()
    for clin in clins:
        award = session.get(Award, clin.award_id)
        hits.append(
            SearchHitOut(
                kind="clin",
                id=clin.clin_id,
                label=f"{award.short_code if award else '?'} CLIN {clin.clin_number}",
                award_id=clin.award_id,
                href=f"/awards/{clin.award_id}",
            )
        )

    documents = session.scalars(
        select(Document).where(func.lower(Document.title).like(pattern)).limit(SEARCH_LIMIT)
    ).all()
    for doc in documents:
        hits.append(
            SearchHitOut(
                kind="document",
                id=doc.document_id,
                label=doc.title,
                award_id=doc.award_id,
                href=f"/awards/{doc.award_id}",
            )
        )

    return SearchOut(query=needle, hits=hits)
