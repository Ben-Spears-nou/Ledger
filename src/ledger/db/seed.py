"""Idempotent runtime seeds that cannot live in schema.sql (password hashes)."""

from __future__ import annotations

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ledger.auth import hash_password
from ledger.config import get_settings
from ledger.db.engine import get_sessionmaker
from ledger.models.identity import Person, UserAccount
from ledger.models.lookups import Organization


def ensure_bootstrap_admin(engine: Engine) -> UserAccount | None:
    """Create the operator admin account if no users exist yet."""
    settings = get_settings()
    factory = get_sessionmaker(engine)
    session = factory()
    try:
        existing = session.scalar(select(UserAccount).limit(1))
        if existing is not None:
            return existing
        org = session.get(Organization, 1)
        if org is None:
            org = Organization(organization_id=1, name="Default Organization")
            session.add(org)
            session.flush()
        person = Person(
            organization_id=org.organization_id,
            display_name=settings.bootstrap_admin_name,
            email=None,
        )
        session.add(person)
        session.flush()
        account = UserAccount(
            person_id=person.person_id,
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role_code="admin",
            is_active=1,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_default_organization_id(session: Session) -> int:
    """Return organization id 1, creating the seed row if needed."""
    org = session.get(Organization, 1)
    if org is None:
        org = Organization(organization_id=1, name="Default Organization")
        session.add(org)
        session.flush()
    return org.organization_id
