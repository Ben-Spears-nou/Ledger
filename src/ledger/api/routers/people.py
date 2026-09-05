"""Admin person and employee-account management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.auth import hash_password
from ledger.db.seed import get_default_organization_id
from ledger.models import Person, UserAccount
from ledger.schemas.auth import PersonCreate, UserOut
from ledger.schemas.schedule import CapacityIn, CapacityOut
from ledger.services.audit import record_event
from ledger.services.schedule import (
    ScheduleError,
    add_person_capacity,
    list_capacity,
    serialize_capacity,
)

router = APIRouter(prefix="/people", tags=["people"])


@router.get("")
def list_people(
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[dict[str, object]]:
    """List people and their optional login."""
    people = session.scalars(select(Person).order_by(Person.display_name)).all()
    accounts = {row.person_id: row for row in session.scalars(select(UserAccount)).all()}
    result: list[dict[str, object]] = []
    for person in people:
        account = accounts.get(person.person_id)
        result.append(
            {
                "person_id": person.person_id,
                "display_name": person.display_name,
                "email": person.email,
                "hire_date": person.hire_date,
                "labor_category": person.labor_category,
                "username": account.username if account else None,
                "role_code": account.role_code if account else None,
            }
        )
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    """Create a person and optionally a login."""
    if payload.username:
        taken = session.scalar(select(UserAccount).where(UserAccount.username == payload.username))
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "username already exists")
        if not payload.password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "password is required with username")
    person = Person(
        organization_id=get_default_organization_id(session),
        display_name=payload.display_name.strip(),
        email=payload.email,
        hire_date=payload.hire_date,
        labor_category=payload.labor_category,
    )
    session.add(person)
    session.flush()
    account = None
    if payload.username and payload.password:
        if payload.role_code not in {"employee", "admin"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "role_code must be employee or admin")
        account = UserAccount(
            person_id=person.person_id,
            username=payload.username,
            password_hash=hash_password(payload.password),
            role_code=payload.role_code,
            is_active=1,
        )
        session.add(account)
        session.flush()
    record_event(
        session,
        action="person_create",
        entity_type="person",
        entity_id=person.person_id,
        actor_user_id=_admin.user_account_id,
        detail={
            "display_name": person.display_name,
            "username": account.username if account else None,
            "role_code": account.role_code if account else None,
        },
    )
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "user": (
            UserOut(
                user_account_id=account.user_account_id,
                person_id=person.person_id,
                username=account.username,
                role_code=account.role_code,
                display_name=person.display_name,
            ).model_dump()
            if account
            else None
        ),
    }


@router.get("/{person_id}/capacity", response_model=list[CapacityOut])
def get_person_capacity(
    person_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[CapacityOut]:
    """Dated available hours/week for one person."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return [serialize_capacity(row) for row in list_capacity(session, person_id)]


@router.post(
    "/{person_id}/capacity",
    response_model=CapacityOut,
    status_code=status.HTTP_201_CREATED,
)
def post_person_capacity(
    person_id: int,
    payload: CapacityIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> CapacityOut:
    """Insert a new dated capacity row; close the previous open row."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    try:
        row = add_person_capacity(session, person, payload, actor_id=admin.user_account_id)
    except ScheduleError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return serialize_capacity(row)
