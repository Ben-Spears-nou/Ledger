"""Login and current-user routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import display_name_for, get_current_user, get_db
from ledger.auth import create_token, hash_password, verify_password
from ledger.config import get_settings
from ledger.models import UserAccount
from ledger.schemas.auth import LoginRequest, PasswordChangeIn, TokenOut, UserOut
from ledger.services.audit import record_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(session: Session, user: UserAccount) -> UserOut:
    return UserOut(
        user_account_id=user.user_account_id,
        person_id=user.person_id,
        username=user.username,
        role_code=user.role_code,
        display_name=display_name_for(session, user),
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> TokenOut:
    """Issue a bearer token."""
    user = session.scalar(select(UserAccount).where(UserAccount.username == payload.username))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        record_event(
            session,
            action="login_failure",
            entity_type="user_account",
            entity_id=payload.username,
        )
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
    token = create_token(
        {"uid": user.user_account_id, "role": user.role_code},
        get_settings().secret_key,
    )
    return TokenOut(access_token=token, user=_user_out(session, user))


@router.get("/me", response_model=UserOut)
def me(
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> UserOut:
    """Return the authenticated account."""
    return _user_out(session, user)


@router.post("/password", response_model=UserOut)
def change_password(
    payload: PasswordChangeIn,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> UserOut:
    """Change the current user's password and invalidate earlier tokens (D20)."""
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "new password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(UTC).isoformat()
    record_event(
        session,
        action="password_change",
        entity_type="user_account",
        entity_id=user.user_account_id,
        actor_user_id=user.user_account_id,
    )
    session.flush()
    return _user_out(session, user)
