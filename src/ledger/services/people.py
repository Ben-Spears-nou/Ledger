"""Admin person login updates: role, active, password reset (D38)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledger.auth import hash_password
from ledger.models import Person, UserAccount
from ledger.schemas.auth import PersonUpdate, UserOut
from ledger.services.audit import record_event


class PeopleError(ValueError):
    """Domain error turned into HTTP 400/409 by the API."""


def serialize_person(person: Person, account: UserAccount | None) -> dict[str, object]:
    """List/detail row for admin People."""
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "email": person.email,
        "hire_date": person.hire_date,
        "labor_category": person.labor_category,
        "username": account.username if account else None,
        "role_code": account.role_code if account else None,
        "is_active": bool(account.is_active) if account else None,
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


def update_person_login(
    session: Session,
    person: Person,
    payload: PersonUpdate,
    *,
    actor_id: int,
) -> dict[str, object]:
    """Patch role and/or active on an existing login."""
    account = account_for(session, person.person_id)
    if account is None:
        raise PeopleError("person has no login")
    if payload.role_code is None and payload.is_active is None:
        raise PeopleError("role_code or is_active is required")
    if payload.role_code is not None and payload.role_code not in {"employee", "admin"}:
        raise PeopleError("role_code must be employee or admin")
    if _would_drop_last_admin(
        session, account, role_code=payload.role_code, is_active=payload.is_active
    ):
        raise PeopleError("cannot demote or deactivate the last active admin")
    if payload.role_code is not None:
        account.role_code = payload.role_code
    if payload.is_active is not None:
        account.is_active = 1 if payload.is_active else 0
    session.flush()
    record_event(
        session,
        action="person_update",
        entity_type="user_account",
        entity_id=account.user_account_id,
        actor_user_id=actor_id,
        detail={
            "person_id": person.person_id,
            "role_code": account.role_code,
            "is_active": bool(account.is_active),
        },
    )
    return serialize_person(person, account)


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
