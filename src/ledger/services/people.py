"""Admin person facts, logins, and unused delete (D38, D45)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledger.auth import hash_password
from ledger.models import (
    Assignment,
    AuditEvent,
    AwardRateOverride,
    Charge,
    Commitment,
    Person,
    PersonCapacity,
    PersonRate,
    TimesheetPeriod,
    UserAccount,
)
from ledger.schemas.auth import PersonUpdate, UserOut
from ledger.services.audit import record_event


class PeopleError(ValueError):
    """Domain error turned into HTTP 400/409 by the API."""


def serialize_person(
    session: Session, person: Person, account: UserAccount | None
) -> dict[str, object]:
    """List/detail row for admin People."""
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "email": person.email,
        "hire_date": person.hire_date,
        "term_date": person.term_date,
        "labor_category": person.labor_category,
        "username": account.username if account else None,
        "role_code": account.role_code if account else None,
        "is_active": bool(account.is_active) if account else None,
        "can_delete": not unused_person_blockers(session, person),
    }


def account_for(session: Session, person_id: int) -> UserAccount | None:
    """Login bound to this person, if any."""
    return session.scalar(select(UserAccount).where(UserAccount.person_id == person_id))


def count_active_admins(session: Session) -> int:
    """Active admin logins. Inactive admins do not count (D38)."""
    return int(
        session.scalar(
            select(func.count())
            .select_from(UserAccount)
            .where(UserAccount.role_code == "admin", UserAccount.is_active == 1)
        )
        or 0
    )


def _would_drop_last_admin(
    session: Session, account: UserAccount, *, role_code: str | None, is_active: bool | None
) -> bool:
    if account.role_code != "admin" or not account.is_active:
        return False
    next_role = role_code if role_code is not None else account.role_code
    next_active = account.is_active if is_active is None else (1 if is_active else 0)
    if next_role == "admin" and next_active:
        return False
    return count_active_admins(session) <= 1


def _iso_date(value: str | None, *, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise PeopleError(f"{field} must be YYYY-MM-DD") from exc


def unused_person_blockers(session: Session, person: Person) -> list[str]:
    """Reasons a person cannot be deleted (D45)."""
    blockers: list[str] = []
    account = account_for(session, person.person_id)
    if account is not None and _would_drop_last_admin(
        session, account, role_code="employee", is_active=False
    ):
        blockers.append("last_admin")
    if session.scalar(
        select(TimesheetPeriod.timesheet_period_id)
        .where(TimesheetPeriod.person_id == person.person_id)
        .limit(1)
    ):
        blockers.append("timesheet")
    if session.scalar(
        select(Charge.charge_id).where(Charge.person_id == person.person_id).limit(1)
    ):
        blockers.append("charge")
    if session.scalar(
        select(Commitment.commitment_id).where(Commitment.person_id == person.person_id).limit(1)
    ):
        blockers.append("commitment")
    if account is not None and session.scalar(
        select(AuditEvent.audit_event_id)
        .where(AuditEvent.actor_user_id == account.user_account_id)
        .limit(1)
    ):
        blockers.append("audit")
    return blockers


def update_person_login(
    session: Session,
    person: Person,
    payload: PersonUpdate,
    *,
    actor_id: int,
) -> dict[str, object]:
    """Patch person facts and/or login role/active (D38, D45)."""
    data = payload.model_dump(exclude_unset=True)
    fact_keys = {"display_name", "email", "hire_date", "term_date", "labor_category"}
    login_keys = {"role_code", "is_active"}
    if not data:
        raise PeopleError("no fields to update")
    account = account_for(session, person.person_id)
    if login_keys & data.keys() and account is None:
        raise PeopleError("person has no login")
    if payload.role_code is not None and payload.role_code not in {"employee", "admin"}:
        raise PeopleError("role_code must be employee or admin")
    if account is not None and _would_drop_last_admin(
        session, account, role_code=payload.role_code, is_active=payload.is_active
    ):
        raise PeopleError("cannot demote or deactivate the last active admin")

    if "display_name" in data:
        name = (data["display_name"] or "").strip()
        if not name:
            raise PeopleError("display_name is required")
        person.display_name = name
    if "email" in data:
        person.email = data["email"] or None
    if "hire_date" in data:
        person.hire_date = _iso_date(data["hire_date"], field="hire_date")
    if "term_date" in data:
        person.term_date = _iso_date(data["term_date"], field="term_date")
    if "labor_category" in data:
        person.labor_category = data["labor_category"] or None
    if account is not None:
        if payload.role_code is not None:
            account.role_code = payload.role_code
        if payload.is_active is not None:
            account.is_active = 1 if payload.is_active else 0
    session.flush()
    record_event(
        session,
        action="person_update",
        entity_type="person" if fact_keys & data.keys() else "user_account",
        entity_id=person.person_id if fact_keys & data.keys() else account.user_account_id,
        actor_user_id=actor_id,
        detail={"person_id": person.person_id, **{key: data[key] for key in data}},
    )
    return serialize_person(session, person, account)


def delete_person(session: Session, person: Person, *, actor_id: int | None) -> None:
    """Remove an unused person and child plan rows (D45)."""
    blockers = unused_person_blockers(session, person)
    if blockers:
        raise PeopleError(
            "cannot delete this person (" + ", ".join(blockers) + "); deactivate instead"
        )
    person_id = person.person_id
    display_name = person.display_name
    for row in session.scalars(select(Assignment).where(Assignment.person_id == person_id)).all():
        session.delete(row)
    for row in session.scalars(
        select(PersonCapacity).where(PersonCapacity.person_id == person_id)
    ).all():
        session.delete(row)
    for row in session.scalars(select(PersonRate).where(PersonRate.person_id == person_id)).all():
        session.delete(row)
    for row in session.scalars(
        select(AwardRateOverride).where(AwardRateOverride.person_id == person_id)
    ).all():
        session.delete(row)
    account = account_for(session, person_id)
    if account is not None:
        session.delete(account)
    session.flush()
    session.delete(person)
    session.flush()
    record_event(
        session,
        action="person_delete",
        entity_type="person",
        entity_id=person_id,
        actor_user_id=actor_id,
        detail={"display_name": display_name},
    )


def reset_person_password(
    session: Session,
    person: Person,
    new_password: str,
    *,
    actor_id: int,
) -> UserOut:
    """Set a new password and invalidate earlier tokens (D20, D38)."""
    account = account_for(session, person.person_id)
    if account is None:
        raise PeopleError("person has no login")
    if not new_password:
        raise PeopleError("new_password is required")
    account.password_hash = hash_password(new_password)
    account.password_changed_at = datetime.now(UTC).isoformat()
    session.flush()
    record_event(
        session,
        action="password_reset",
        entity_type="user_account",
        entity_id=account.user_account_id,
        actor_user_id=actor_id,
        detail={"person_id": person.person_id},
    )
    return UserOut(
        user_account_id=account.user_account_id,
        person_id=person.person_id,
        username=account.username,
        role_code=account.role_code,
        display_name=person.display_name,
    )
