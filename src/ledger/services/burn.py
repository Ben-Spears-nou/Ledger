"""Integer burn, EAC, runway, and computed alerts (D33–D34)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import column, func, select, table
from sqlalchemy.orm import Session

from ledger.models import Award, Charge
from ledger.schemas.pipeline import AlertOut, AwardBurnOut, BurnMonthOut
from ledger.services.awards import remaining_for

BURN_WINDOW_DAYS = 90
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


def award_burn(session: Session, award: Award, *, as_of: str | None) -> AwardBurnOut:
    """Monthly series plus EAC and runway for one award."""
    as_of_d = _as_of(as_of)
    pop_start = date.fromisoformat(award.pop_start)
    pop_end = date.fromisoformat(award.pop_end)
    window_end = as_of_d
    window_start = max(pop_start, as_of_d - timedelta(days=BURN_WINDOW_DAYS - 1))
    if window_start > window_end:
        window_days = 0
        window_actual = 0
        daily = 0
    else:
        window_days = (window_end - window_start).days + 1
        window_actual = window_actual_cents(
            session, award.award_id, window_start=window_start, window_end=window_end
        )
        daily = window_actual // window_days if window_days else 0
    remaining = remaining_for(session, award.award_id)
    actual = actual_as_of(session, award.award_id, as_of_d)
    remaining_approved = remaining.remaining_approved_cents if remaining is not None else 0
    days_left = max((pop_end - as_of_d).days, 0)
    eac = actual + daily * days_left
    runway = remaining_approved // daily if daily else None
    if runway is not None:
        runway = max(runway, 0)
    return AwardBurnOut(
        award_id=award.award_id,
        as_of=as_of_d.isoformat(),
        actual_cents=actual,
        remaining_approved_cents=remaining_approved,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        window_actual_cents=window_actual,
        window_days=window_days,
        daily_burn_cents=daily,
        days_to_pop_end=days_left,
        eac_cents=eac,
        runway_days=runway,
        months=monthly_burn(session, award.award_id, as_of=as_of_d),
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
