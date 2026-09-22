"""Integer burn, EAC, runway, and computed alerts (D33–D34)."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import column, func, or_, select, table
from sqlalchemy.orm import Session

from ledger.models import (
    Assignment,
    Award,
    Charge,
    Commitment,
    FundingExpectation,
    Person,
)
from ledger.rates import loaded_rate_cents
from ledger.schemas.pipeline import (
    AlertOut,
    AwardBurnOut,
    BurnMonthOut,
    BurnWindowOut,
    ForecastMonthOut,
)
from ledger.services.awards import remaining_for
from ledger.services.schedule import projected_assignment_for_month
from ledger.services.time import amount_cents_for, as_of_policy, as_of_rate, override_for

BURN_WINDOW_DAYS = 90
BURN_WINDOWS = (30, 60, 90)
POP_ALERT_DAYS = 30


class BurnError(ValueError):
    """Domain error turned into HTTP 400/404 by the API."""


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise BurnError(f"{field} must be YYYY-MM-DD") from exc


def _as_of(value: str | None) -> date:
    if value:
        return date.fromisoformat(_iso_date(value, field="as_of"))
    return datetime.now(UTC).date()


def monthly_burn(session: Session, award_id: int, *, as_of: date) -> list[BurnMonthOut]:
    """Posted actuals by YYYY-MM, up to as_of's month."""
    view = table(
        "v_award_burn_monthly",
        column("award_id"),
        column("year_month"),
        column("actual_cents"),
    )
    cutoff = as_of.isoformat()[:7]
    rows = session.execute(
        select(view)
        .where(column("award_id") == award_id)
        .where(column("year_month") <= cutoff)
        .order_by(column("year_month"))
    ).mappings()
    return [
        BurnMonthOut(year_month=str(row["year_month"]), actual_cents=int(row["actual_cents"]))
        for row in rows
    ]


def window_actual_cents(
    session: Session,
    award_id: int,
    *,
    window_start: date,
    window_end: date,
) -> int:
    """Sum charges in [window_start, window_end] with a work_date."""
    value = session.scalar(
        select(func.coalesce(func.sum(Charge.amount_cents), 0)).where(
            Charge.award_id == award_id,
            Charge.work_date.is_not(None),
            Charge.work_date >= window_start.isoformat(),
            Charge.work_date <= window_end.isoformat(),
        )
    )
    return int(value or 0)


def actual_as_of(session: Session, award_id: int, as_of: date) -> int:
    """Posted actuals with work_date on or before as_of."""
    return window_actual_cents(session, award_id, window_start=date.min, window_end=as_of)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    return (value.replace(day=28) + timedelta(days=4)).replace(day=1)


def _month_starts(first: date, last: date) -> list[date]:
    current = _month_start(first)
    end = _month_start(last)
    result: list[date] = []
    while current <= end:
        result.append(current)
        current = _next_month(current)
    return result


def _window(session: Session, award: Award, as_of: date, days: int) -> BurnWindowOut:
    pop_start = date.fromisoformat(award.pop_start)
    window_end = as_of
    window_start = max(pop_start, as_of - timedelta(days=days - 1))
    if window_start > window_end:
        elapsed = 0
        actual = 0
    else:
        elapsed = (window_end - window_start).days + 1
        actual = window_actual_cents(
            session,
            award.award_id,
            window_start=window_start,
            window_end=window_end,
        )
    daily = actual // elapsed if elapsed else 0
    return BurnWindowOut(
        days=days,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        actual_cents=actual,
        daily_burn_cents=daily,
        monthly_rate_cents=daily * 30,
    )


def _planned_cents_for_month(session: Session, award: Award, month_start: date) -> int | None:
    """Loaded labor plan for assignments overlapping one calendar month."""
    month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
    rows = session.scalars(
        select(Assignment).where(
            Assignment.award_id == award.award_id,
            Assignment.effective_from <= month_end.isoformat(),
            or_(
                Assignment.effective_to.is_(None),
                Assignment.effective_to >= month_start.isoformat(),
            ),
        )
    ).all()
    total = 0
    missing_rate = False
    for row in rows:
        hours = projected_assignment_for_month(row, month_start.isoformat())
        if hours <= 0:
            continue
        person = session.get(Person, row.person_id)
        rate_date = max(month_start, date.fromisoformat(row.effective_from)).isoformat()
        rate = as_of_rate(session, row.person_id, rate_date)
        policy = as_of_policy(session, award.award_id, rate_date)
        if person is None or rate is None or policy is None:
            missing_rate = True
            continue
        override = override_for(session, policy, person)
        try:
            loaded = loaded_rate_cents(
                rate.base_rate_cents,
                policy,
                override.loaded_rate_cents if override else None,
            )
        except ValueError:
            missing_rate = True
            continue
        total += amount_cents_for(hours, loaded)
    if missing_rate:
        return None
    return total


def _forecast_months(
    session: Session,
    award: Award,
    *,
    as_of: date,
    daily_burn_cents: int,
) -> list[ForecastMonthOut]:
    """Build one integrated monthly series without changing stored balances."""
    pop_start = date.fromisoformat(award.pop_start)
    pop_end = date.fromisoformat(award.pop_end)
    actual_by_month = {
        row.year_month: row.actual_cents
        for row in monthly_burn(session, award.award_id, as_of=as_of)
    }
    commitments: dict[str, int] = {}
    for row in session.scalars(
        select(Commitment).where(
            Commitment.award_id == award.award_id,
            Commitment.status_code == "open",
        )
    ):
        when = row.expected_date or row.effective_date
        commitments[when[:7]] = commitments.get(when[:7], 0) + row.amount_cents
    funding: dict[str, int] = {}
    for row in session.scalars(
        select(FundingExpectation).where(FundingExpectation.award_id == award.award_id)
    ):
        key = row.expected_date[:7]
        funding[key] = funding.get(key, 0) + row.amount_cents

    dated_months = [date.fromisoformat(f"{key}-01") for key in commitments | funding]
    last = max([pop_end, as_of, *dated_months])
    cumulative = 0
    actual_total = actual_as_of(session, award.award_id, as_of)
    output: list[ForecastMonthOut] = []
    for month in _month_starts(pop_start, last):
        key = month.strftime("%Y-%m")
        actual = actual_by_month.get(key, 0)
        cumulative += actual
        month_end = month.replace(day=monthrange(month.year, month.month)[1])
        if month_end <= as_of:
            projected = cumulative
        elif month <= as_of <= month_end:
            projected = actual_total + daily_burn_cents * max((month_end - as_of).days, 0)
        else:
            through = min(month_end, pop_end)
            projected = actual_total + daily_burn_cents * max((through - as_of).days, 0)
        output.append(
            ForecastMonthOut(
                year_month=key,
                actual_cents=actual,
                cumulative_actual_cents=cumulative,
                planned_cents=_planned_cents_for_month(session, award, month),
                commitment_cents=commitments.get(key, 0),
                funding_expected_cents=funding.get(key, 0),
                projected_cumulative_cents=projected,
            )
        )
    return output


def award_burn(
    session: Session,
    award: Award,
    *,
    as_of: str | None,
    window_days: int = BURN_WINDOW_DAYS,
) -> AwardBurnOut:
    """Monthly series plus EAC and runway for one award."""
    if window_days not in BURN_WINDOWS:
        raise BurnError("window_days must be 30, 60, or 90")
    as_of_d = _as_of(as_of)
    pop_end = date.fromisoformat(award.pop_end)
    windows = [_window(session, award, as_of_d, days) for days in BURN_WINDOWS]
    selected = next(row for row in windows if row.days == window_days)
    daily = selected.daily_burn_cents
    remaining = remaining_for(session, award.award_id)
    actual = actual_as_of(session, award.award_id, as_of_d)
    remaining_approved = remaining.remaining_approved_cents if remaining is not None else 0
    approved_ceiling = remaining.approved_cents if remaining is not None else 0
    funded_ceiling = remaining.funded_amount_cents if remaining is not None else 0
    committed = remaining.committed_cents if remaining is not None else 0
    days_left = max((pop_end - as_of_d).days, 0)
    eac = actual + daily * days_left
    runway = remaining_approved // daily if daily else None
    if runway is not None:
        runway = max(runway, 0)
    runway_end = (as_of_d + timedelta(days=runway)).isoformat() if runway is not None else None
    return AwardBurnOut(
        award_id=award.award_id,
        as_of=as_of_d.isoformat(),
        actual_cents=actual,
        remaining_approved_cents=remaining_approved,
        window_start=selected.window_start,
        window_end=selected.window_end,
        window_actual_cents=selected.actual_cents,
        window_days=window_days,
        selected_window_days=window_days,
        daily_burn_cents=daily,
        days_to_pop_end=days_left,
        eac_cents=eac,
        runway_days=runway,
        approved_ceiling_cents=approved_ceiling,
        funded_ceiling_cents=funded_ceiling,
        committed_cents=committed,
        runway_end=runway_end,
        windows=windows,
        months=monthly_burn(session, award.award_id, as_of=as_of_d),
        forecast_months=_forecast_months(
            session,
            award,
            as_of=as_of_d,
            daily_burn_cents=daily,
        ),
    )


def list_alerts(
    session: Session,
    *,
    as_of: str | None = None,
    award_id: int | None = None,
) -> list[AlertOut]:
    """Computed burn and PoP warnings for active awards."""
    as_of_d = _as_of(as_of)
    stmt = select(Award).where(Award.status_code == "active").order_by(Award.short_code)
    if award_id is not None:
        stmt = stmt.where(Award.award_id == award_id)
    alerts: list[AlertOut] = []
    for award in session.scalars(stmt):
        remaining = remaining_for(session, award.award_id)
        actual = actual_as_of(session, award.award_id, as_of_d)
        approved = remaining.approved_cents if remaining is not None else 0
        basis = award.funded_amount_cents if award.enforce_ceiling else approved
        if basis > 0 and actual * 100 >= basis * award.ceiling_warn_pct:
            alerts.append(
                AlertOut(
                    alert_code="burn_ceiling",
                    award_id=award.award_id,
                    award_short_code=award.short_code,
                    as_of=as_of_d.isoformat(),
                    actual_cents=actual,
                    basis_cents=basis,
                    ceiling_warn_pct=award.ceiling_warn_pct,
                )
            )
        pop_end = date.fromisoformat(award.pop_end)
        days_left = (pop_end - as_of_d).days
        if days_left <= POP_ALERT_DAYS:
            alerts.append(
                AlertOut(
                    alert_code="pop_end",
                    award_id=award.award_id,
                    award_short_code=award.short_code,
                    as_of=as_of_d.isoformat(),
                    pop_end=award.pop_end,
                    days_to_pop_end=days_left,
                )
            )
    return alerts
