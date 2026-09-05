"""FastAPI dependencies: database session and current user."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ledger.auth import read_token
from ledger.config import get_settings
from ledger.db.engine import get_engine, get_sessionmaker
from ledger.models import Person, UserAccount

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    """Yield a request-scoped session."""
    factory = get_sessionmaker(get_engine())
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_db),
) -> UserAccount:
    """Require a valid bearer token."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = read_token(creds.credentials, get_settings().secret_key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = session.get(UserAccount, int(payload["uid"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown or inactive user")
    try:
        read_token(
            creds.credentials,
            get_settings().secret_key,
            password_changed_at=user.password_changed_at,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return user


def require_admin(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    """Reject non-admin callers."""
    if user.role_code != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin role required")
    return user


def display_name_for(session: Session, user: UserAccount) -> str:
    """Return the person's display name."""
    person = session.get(Person, user.person_id)
    return person.display_name if person else user.username
