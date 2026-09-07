"""Pydantic payloads for login."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Username and password."""

    username: str
    password: str


class PasswordChangeIn(BaseModel):
    """Logged-in user changing their own password."""

    current_password: str
    new_password: str = Field(min_length=1)


class UserOut(BaseModel):
    """Public account fields."""

    user_account_id: int
    person_id: int
    username: str
    role_code: str
    display_name: str


class TokenOut(BaseModel):
    """Bearer token returned by login."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PersonCreate(BaseModel):
    """Admin-created employee (optional login)."""

    display_name: str
    email: str | None = None
    hire_date: str | None = None
    labor_category: str | None = None
    username: str | None = None
    password: str | None = None
    role_code: str = Field(default="employee")


class PersonUpdate(BaseModel):
    """Admin patch of person facts and/or login (D38, D45). Username is not changed."""

    display_name: str | None = None
    email: str | None = None
    hire_date: str | None = None
    term_date: str | None = None
    labor_category: str | None = None
    role_code: str | None = None
    is_active: bool | None = None


class AdminPasswordResetIn(BaseModel):
    """Admin-set password. Does not require the current password."""

    new_password: str = Field(min_length=1)
