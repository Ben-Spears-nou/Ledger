"""Timesheets, dated base rates, and labor charge posting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ledger.models import (
    Award,
    AwardRateOverride,
    AwardRatePolicy,
    BudgetLine,
    Charge,
    Person,
    PersonRate,
    TimeCode,
    TimesheetLine,
    TimesheetPeriod,
    UserAccount,
)
from ledger.rates import loaded_rate_cents
from ledger.services.audit import record_event
from ledger.services.awards import line_remaining_map, remaining_for


class TimeError(ValueError):
    """Domain error turned into HTTP 400/409 by the API."""


def week_start_on_or_before(iso_date: str) -> str:
    """Return the Monday of the week containing ``iso_date``."""
    parsed = date.fromisoformat(iso_date)
    return (parsed - timedelta(days=parsed.weekday())).isoformat()


def hours_to_hundredths(hours: float) -> int:
    """Convert hours to integer hundredths (2.5 → 250)."""
    hundredths = round(hours * 100)
    if hundredths <= 0:
        raise TimeError("hours must be greater than zero")
    return hundredths


def hundredths_to_hours(hundredths: int) -> float:
    """Convert stored hundredths to hours."""
    return hundredths / 100.0


def amount_cents_for(hours_hundredths: int, loaded: int) -> int:
    """``hours × loaded rate``, rounded to cents."""
    return round(hours_hundredths * loaded / 100)


def _as_of_rate(session: Session, person_id: int, work_date: str) -> PersonRate | None:
    return session.scalar(
        select(PersonRate)
        .where(
            PersonRate.person_id == person_id,
            PersonRate.effective_from <= work_date,
            or_(PersonRate.effective_to.is_(None), PersonRate.effective_to >= work_date),
        )
        .order_by(PersonRate.effective_from.desc())
    )


def _as_of_policy(session: Session, award_id: int, work_date: str) -> AwardRatePolicy | None:
    return session.scalar(
        select(AwardRatePolicy)
        .where(
            AwardRatePolicy.award_id == award_id,
            AwardRatePolicy.effective_from <= work_date,
            or_(AwardRatePolicy.effective_to.is_(None), AwardRatePolicy.effective_to >= work_date),
        )
        .order_by(AwardRatePolicy.effective_from.desc())
    )


def _override_for(
    session: Session, policy: AwardRatePolicy, person: Person
) -> AwardRateOverride | None:
    by_person = session.scalar(
        select(AwardRateOverride).where(
            AwardRateOverride.policy_id == policy.policy_id,
            AwardRateOverride.person_id == person.person_id,
        )
    )
    if by_person is not None:
        return by_person
    if not person.labor_category:
        return None
    return session.scalar(
        select(AwardRateOverride).where(
            AwardRateOverride.policy_id == policy.policy_id,
            AwardRateOverride.labor_category == person.labor_category,
        )
    )


def as_of_rate(session: Session, person_id: int, work_date: str) -> PersonRate | None:
    """Person base-rate row in effect on ``work_date``."""
    return _as_of_rate(session, person_id, work_date)


def as_of_policy(session: Session, award_id: int, work_date: str) -> AwardRatePolicy | None:
    """Award rate policy in effect on ``work_date``."""
    return _as_of_policy(session, award_id, work_date)


def override_for(
    session: Session, policy: AwardRatePolicy, person: Person
) -> AwardRateOverride | None:
    """Person or labor-category loaded-rate override, if any."""
    return _override_for(session, policy, person)


@dataclass(frozen=True)
class LaborPreview:
    """Computed loaded rate for one timesheet line (not stored on the line)."""

    hours_hundredths: int
    base_rate_cents: int
    loaded_rate_cents: int
    amount_cents: int
    person_rate_id: int
    policy_id: int
    override_id: int | None
    fringe_pct: int
    oh_pct: int
    ga_pct: int
    fee_pct: int
    fee_in_burden: int
    budget_line_id: int | None
    category_code: str | None


def preview_labor_line(session: Session, person: Person, line: TimesheetLine) -> LaborPreview:
    """Compute dollars for an award line using rates as-of the work date."""
    if line.award_id is None:
        raise TimeError("award hours require an award_id")
    award = session.get(Award, line.award_id)
    if award is None:
        raise TimeError("award not found")
    if award.status_code == "closed":
        raise TimeError("cannot post time to a closed award")
    person_rate = _as_of_rate(session, person.person_id, line.work_date)
    if person_rate is None:
        raise TimeError(f"no base rate for this person on {line.work_date}")
    policy = _as_of_policy(session, award.award_id, line.work_date)
    if policy is None:
        raise TimeError(f"no rate policy for award {award.short_code} on {line.work_date}")
    override = _override_for(session, policy, person)
    override_cents = override.loaded_rate_cents if override else None
    try:
        loaded = loaded_rate_cents(person_rate.base_rate_cents, policy, override_cents)
    except ValueError as exc:
        raise TimeError(str(exc)) from exc
    budget_line = None
    if policy.labor_budget_line_id is not None:
        budget_line = session.get(BudgetLine, policy.labor_budget_line_id)
    category = budget_line.category_code if budget_line else "personnel"
    return LaborPreview(
        hours_hundredths=line.hours_hundredths,
        base_rate_cents=person_rate.base_rate_cents,
        loaded_rate_cents=loaded,
        amount_cents=amount_cents_for(line.hours_hundredths, loaded),
        person_rate_id=person_rate.person_rate_id,
        policy_id=policy.policy_id,
        override_id=override.override_id if override else None,
        fringe_pct=policy.fringe_pct,
        oh_pct=policy.oh_pct,
        ga_pct=policy.ga_pct,
        fee_pct=policy.fee_pct,
        fee_in_burden=policy.fee_in_burden,
        budget_line_id=policy.labor_budget_line_id,
        category_code=category,
    )


def close_open_person_rates(session: Session, person_id: int, new_from: str) -> None:
    """Close the open base-rate row. Does not overwrite history (D5)."""
    open_rows = session.scalars(
        select(PersonRate).where(
            PersonRate.person_id == person_id,
            PersonRate.effective_to.is_(None),
        )
    ).all()
    parsed = date.fromisoformat(new_from)
    closed_on = (parsed - timedelta(days=1)).isoformat()
    for row in open_rows:
        row.effective_to = closed_on if closed_on >= row.effective_from else new_from


def add_person_rate(
    session: Session,
    person: Person,
    *,
    effective_from: str,
    base_rate_cents: int | None,
    salary_cents: int | None,
    hours_per_year: int | None,
    actor_id: int | None = None,
) -> PersonRate:
    """Insert a dated base rate. Salary + hours/year derives the hourly rate."""
    hourly = base_rate_cents
    if salary_cents is not None:
        if not hours_per_year:
            raise TimeError("hours_per_year is required when salary_cents is set")
        hourly = round(salary_cents / hours_per_year)
    if hourly is None:
        raise TimeError("base_rate_cents or salary_cents is required")
    close_open_person_rates(session, person.person_id, effective_from)
    row = PersonRate(
        person_id=person.person_id,
        effective_from=effective_from,
        effective_to=None,
        base_rate_cents=hourly,
        hours_per_year=hours_per_year,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="person_rate_create",
        entity_type="person_rate",
        entity_id=row.person_rate_id,
        actor_user_id=actor_id,
        detail={"person_id": person.person_id, "effective_from": effective_from},
    )
    return row


def delete_person_rate(session: Session, row: PersonRate, *, actor_id: int | None) -> None:
    """Remove an unused base-rate row and reopen the predecessor (D45)."""
    used = session.scalar(
        select(Charge.charge_id).where(Charge.person_rate_id == row.person_rate_id).limit(1)
    )
    if used is not None:
        raise TimeError("cannot delete a rate that priced a posted charge")
    from ledger.services.schedule import reopen_dated_predecessor

    siblings = list(
        session.scalars(
            select(PersonRate)
            .where(
                PersonRate.person_id == row.person_id,
                PersonRate.person_rate_id != row.person_rate_id,
            )
            .order_by(PersonRate.effective_from)
        )
    )
    rate_id = row.person_rate_id
    person_id = row.person_id
    reopen_dated_predecessor(siblings, row)
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="person_rate_delete",
        entity_type="person_rate",
        entity_id=rate_id,
        actor_user_id=actor_id,
        detail={"person_id": person_id},
    )


def _time_code_row(session: Session, code: str) -> TimeCode:
    row = session.get(TimeCode, code)
    if row is None:
        raise TimeError(f"unknown time_code: {code}")
    return row


def _task_belongs_to_award(session: Session, task_id: int, award_id: int) -> None:
    """Raise if the task is missing, closed, or on another award."""
    from ledger.models import Task

    task = session.get(Task, task_id)
    if task is None:
        raise TimeError("task not found")
    if task.award_id != award_id:
        raise TimeError("task does not belong to this award")
    if task.status_code == "closed":
        raise TimeError("cannot post time to a closed task")


def _validate_line_spec(
    session: Session, work_date: str, week_start: str, spec: dict[str, object]
) -> None:
    monday = week_start_on_or_before(week_start)
    parsed = date.fromisoformat(work_date)
    week_end = date.fromisoformat(monday) + timedelta(days=6)
    if parsed < date.fromisoformat(monday) or parsed > week_end:
        raise TimeError(f"{work_date} is not in the week starting {monday}")
    time_code = str(spec.get("time_code") or ("award" if spec.get("award_id") else ""))
    if not time_code:
        raise TimeError("each line needs time_code or award_id")
    code = _time_code_row(session, time_code)
    award_id = spec.get("award_id")
    task_id = spec.get("task_id")
    if code.consumes_award:
        if award_id is None:
            raise TimeError("award hours require award_id")
        award = session.get(Award, int(award_id))
        if award is None:
            raise TimeError("award not found")
        if award.status_code == "closed":
            raise TimeError("cannot post time to a closed award")
        if task_id is not None:
            _task_belongs_to_award(session, int(task_id), int(award_id))
    else:
        if award_id is not None:
            raise TimeError(f"{time_code} hours cannot be charged to an award")
        if task_id is not None:
            raise TimeError(f"{time_code} hours cannot carry a task")


def get_or_create_period(
    session: Session, person_id: int, week_start: str, *, prefill: bool = False
) -> TimesheetPeriod:
    """Return the week row, creating a draft if needed.

    When ``prefill`` is true and the period is newly created, copy overlapping
    assignments onto the empty draft (D7, D23). Existing periods are left alone.
    """
    monday = week_start_on_or_before(week_start)
    period = session.scalar(
        select(TimesheetPeriod).where(
            TimesheetPeriod.person_id == person_id,
            TimesheetPeriod.week_start == monday,
        )
    )
    if period is None:
        period = TimesheetPeriod(
            person_id=person_id,
            week_start=monday,
            status_code="draft",
        )
        session.add(period)
        session.flush()
        if prefill:
            from ledger.services.schedule import prefill_period_from_assignments

            prefill_period_from_assignments(session, period)
    return period


def replace_week_lines(
    session: Session,
    period: TimesheetPeriod,
    lines: list[dict[str, object]],
) -> TimesheetPeriod:
    """Replace all lines on a draft/returned week. No hour-total rules (D10)."""
    if period.status_code not in {"draft", "returned"}:
        raise TimeError("only draft or returned weeks can be edited")
    existing = session.scalars(
        select(TimesheetLine).where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()
    for spec in lines:
        work_date = str(spec["work_date"])
        _validate_line_spec(session, work_date, period.week_start, spec)
        hours = hours_to_hundredths(float(spec["hours"]))  # type: ignore[arg-type]
        time_code = str(spec.get("time_code") or "award")
        award_id = int(spec["award_id"]) if spec.get("award_id") is not None else None
        task_id = int(spec["task_id"]) if spec.get("task_id") is not None else None
        session.add(
            TimesheetLine(
                timesheet_period_id=period.timesheet_period_id,
                work_date=work_date,
                hours_hundredths=hours,
                time_code=time_code,
                award_id=award_id,
                task_id=task_id,
            )
        )
    period.return_comment = None
    session.flush()
    return period


def submit_period(
    session: Session, period: TimesheetPeriod, *, actor_id: int | None = None
) -> TimesheetPeriod:
    """Move draft/returned → submitted. Hours may total anything (D10)."""
    if period.status_code not in {"draft", "returned"}:
        raise TimeError("week is already submitted or approved")
    period.status_code = "submitted"
    period.submitted_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    period.return_comment = None
    session.flush()
    record_event(
        session,
        action="week_submit",
        entity_type="timesheet_period",
        entity_id=period.timesheet_period_id,
        actor_user_id=actor_id,
        detail={"person_id": period.person_id, "week_start": period.week_start},
    )
    return period


def return_period(
    session: Session,
    period: TimesheetPeriod,
    comment: str,
    *,
    actor_id: int | None = None,
) -> TimesheetPeriod:
    """Bounce a submitted week back to draft."""
    if period.status_code != "submitted":
        raise TimeError("only submitted weeks can be returned")
    period.status_code = "returned"
    period.return_comment = comment
    session.flush()
    record_event(
        session,
        action="week_return",
        entity_type="timesheet_period",
        entity_id=period.timesheet_period_id,
        actor_user_id=actor_id,
        detail={"person_id": period.person_id, "week_start": period.week_start},
    )
    return period


def _existing_labor_charge(session: Session, line_id: int) -> Charge | None:
    return session.scalar(
        select(Charge).where(
            Charge.timesheet_line_id == line_id,
            Charge.source == "labor",
            Charge.reverses_charge_id.is_(None),
        )
    )


def approve_warnings(session: Session, period: TimesheetPeriod) -> list[str]:
    """Informational approve messages (D43). Never used on employee submit."""
    from ledger.services.schedule import overlapping_assignments

    person = session.get(Person, period.person_id)
    if person is None:
        return []
    lines = session.scalars(
        select(TimesheetLine).where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
    ).all()
    hours_by_award: dict[int, int] = {}
    extras: dict[int, int] = {}
    for line in lines:
        code = _time_code_row(session, line.time_code)
        if not code.consumes_award or line.award_id is None:
            continue
        hours_by_award[line.award_id] = hours_by_award.get(line.award_id, 0) + line.hours_hundredths
        try:
            preview = preview_labor_line(session, person, line)
        except TimeError:
            continue
        extras[line.award_id] = extras.get(line.award_id, 0) + preview.amount_cents
    assigned: dict[int, int] = {}
    for row in overlapping_assignments(session, period.person_id, period.week_start):
        assigned[row.award_id] = assigned.get(row.award_id, 0) + row.hours_hundredths_per_week
    warnings: list[str] = []
    for award_id, hundredths in hours_by_award.items():
        award = session.get(Award, award_id)
        if award is None:
            continue
        planned = assigned.get(award_id, 0)
        if hundredths > planned + 1:
            warnings.append(
                f"{award.short_code}: logged {hundredths_to_hours(hundredths)}h exceeds "
                f"assigned {hundredths_to_hours(planned)}h"
            )
        extra = extras.get(award_id, 0)
        remaining = remaining_for(session, award_id)
        if remaining is None:
            continue
        policy = award.overrun_policy or "warn"
        if policy == "allow":
            continue
        if remaining.remaining_funded_cents - extra < 0:
            warnings.append(
                f"{award.short_code}: this week would exceed funded remaining "
                f"({remaining.remaining_funded_cents} cents)"
            )
        dated_policy = _as_of_policy(session, award.award_id, period.week_start)
        if dated_policy is not None and dated_policy.labor_budget_line_id is not None:
            money = line_remaining_map(session, award.award_id)
            personnel = money.get(dated_policy.labor_budget_line_id, (0, 0, 0))[2]
            if personnel - extra < 0:
                warnings.append(
                    f"{award.short_code}: this week would exceed remaining personnel "
                    f"({personnel} cents)"
                )
    return warnings


def approve_period(
    session: Session, period: TimesheetPeriod, admin: UserAccount
) -> TimesheetPeriod:
    """Post labor charges and mark the week approved."""
    if period.status_code == "approved":
        raise TimeError("week is already approved")
    if period.status_code != "submitted":
        raise TimeError("only submitted weeks can be approved")
    person = session.get(Person, period.person_id)
    if person is None:
        raise TimeError("person not found")
    lines = session.scalars(
        select(TimesheetLine).where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
    ).all()
    previews: list[tuple[TimesheetLine, LaborPreview | None]] = []
    extras: dict[int, int] = {}
    for line in lines:
        if _existing_labor_charge(session, line.timesheet_line_id):
            raise TimeError("this week already has posted charges")
        code = _time_code_row(session, line.time_code)
        if not code.consumes_award:
            previews.append((line, None))
            continue
        preview = preview_labor_line(session, person, line)
        previews.append((line, preview))
        assert line.award_id is not None
        extras[line.award_id] = extras.get(line.award_id, 0) + preview.amount_cents

    for award_id, extra in extras.items():
        award = session.get(Award, award_id)
        if award is None:
            raise TimeError("award not found")
        if not award.enforce_ceiling:
            continue
        remaining = remaining_for(session, award_id)
        if remaining is None:
            continue
        if remaining.remaining_funded_cents - extra < 0:
            raise TimeError(
                f"{award.short_code} would exceed funded remaining "
                f"({remaining.remaining_funded_cents} cents)"
            )

    for line, preview in previews:
        if preview is None:
            continue
        session.add(
            Charge(
                source="labor",
                timesheet_line_id=line.timesheet_line_id,
                award_id=line.award_id,
                budget_line_id=preview.budget_line_id,
                category_code=preview.category_code,
                person_id=person.person_id,
                work_date=line.work_date,
                hours_hundredths=preview.hours_hundredths,
                amount_cents=preview.amount_cents,
                base_rate_cents=preview.base_rate_cents,
                fringe_pct=preview.fringe_pct,
                oh_pct=preview.oh_pct,
                ga_pct=preview.ga_pct,
                fee_pct=preview.fee_pct,
                fee_in_burden=preview.fee_in_burden,
                loaded_rate_cents=preview.loaded_rate_cents,
                person_rate_id=preview.person_rate_id,
                policy_id=preview.policy_id,
                override_id=preview.override_id,
                created_by=admin.user_account_id,
            )
        )
    period.status_code = "approved"
    period.approved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    period.approved_by = admin.user_account_id
    session.flush()
    record_event(
        session,
        action="week_approve",
        entity_type="timesheet_period",
        entity_id=period.timesheet_period_id,
        actor_user_id=admin.user_account_id,
        detail={"person_id": period.person_id, "week_start": period.week_start},
    )
    return period


def reverse_charge(session: Session, charge: Charge, *, actor_id: int | None) -> Charge:
    """Insert an opposite charge. Does not edit the original (D5)."""
    reversal = Charge(
        source="reversal",
        timesheet_line_id=charge.timesheet_line_id,
        award_id=charge.award_id,
        budget_line_id=charge.budget_line_id,
        category_code=charge.category_code,
        person_id=charge.person_id,
        work_date=charge.work_date,
        hours_hundredths=(
            -charge.hours_hundredths if charge.hours_hundredths is not None else None
        ),
        amount_cents=-charge.amount_cents,
        base_rate_cents=charge.base_rate_cents,
        fringe_pct=charge.fringe_pct,
        oh_pct=charge.oh_pct,
        ga_pct=charge.ga_pct,
        fee_pct=charge.fee_pct,
        fee_in_burden=charge.fee_in_burden,
        loaded_rate_cents=charge.loaded_rate_cents,
        person_rate_id=charge.person_rate_id,
        policy_id=charge.policy_id,
        override_id=charge.override_id,
        reverses_charge_id=charge.charge_id,
        created_by=actor_id,
    )
    session.add(reversal)
    session.flush()
    return reversal


def period_hours_total(session: Session, period: TimesheetPeriod) -> float:
    """Informational week total. Not a constraint."""
    lines = session.scalars(
        select(TimesheetLine).where(TimesheetLine.timesheet_period_id == period.timesheet_period_id)
    ).all()
    return sum(hundredths_to_hours(line.hours_hundredths) for line in lines)
