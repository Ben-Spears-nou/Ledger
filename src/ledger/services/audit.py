"""Append-only audit writes and admin list/CSV helpers (D19, D35–D36)."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledger.models import AuditEvent, Award, Charge, Person, UserAccount

DEFAULT_AUDIT_LIMIT = 500
MAX_AUDIT_LIMIT = 2000

CHARGE_CSV_COLUMNS = (
    "charge_id",
    "source",
    "award_id",
    "award_short_code",
    "category_code",
    "person_id",
    "work_date",
    "hours_hundredths",
    "amount_cents",
    "reverses_charge_id",
    "created_at",
)


class AuditError(ValueError):
    """Domain error turned into HTTP 400 by the API."""


def record_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    actor_user_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Insert one audit row. Never store a password in ``detail``."""
    row = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        detail=json.dumps(detail, separators=(",", ":"), sort_keys=True) if detail else None,
    )
    session.add(row)
    session.flush()
    return row


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise AuditError(f"{field} must be YYYY-MM-DD") from exc


def _parse_detail(raw: str | None) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def serialize_audit(row: AuditEvent, actor_display_name: str | None) -> dict[str, object]:
    """JSON row for the admin list. Existing keys stay (D35)."""
    return {
        "audit_event_id": row.audit_event_id,
        "occurred_at": row.occurred_at,
        "actor_user_id": row.actor_user_id,
        "actor_display_name": actor_display_name,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "detail": _parse_detail(row.detail),
    }


def list_audit_events(
    session: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    occurred_from: str | None = None,
    occurred_to: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Newest-first audit rows with optional filters."""
    cap = DEFAULT_AUDIT_LIMIT if limit is None else int(limit)
    if cap < 1 or cap > MAX_AUDIT_LIMIT:
        raise AuditError(f"limit must be between 1 and {MAX_AUDIT_LIMIT}")
    stmt = (
        select(AuditEvent, Person.display_name)
        .outerjoin(UserAccount, UserAccount.user_account_id == AuditEvent.actor_user_id)
        .outerjoin(Person, Person.person_id == UserAccount.person_id)
        .order_by(AuditEvent.audit_event_id.desc())
        .limit(cap)
    )
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if occurred_from:
        start = _iso_date(occurred_from, field="occurred_from")
        stmt = stmt.where(func.substr(AuditEvent.occurred_at, 1, 10) >= start)
    if occurred_to:
        end = _iso_date(occurred_to, field="occurred_to")
        stmt = stmt.where(func.substr(AuditEvent.occurred_at, 1, 10) <= end)
    rows = session.execute(stmt).all()
    return [serialize_audit(event, name) for event, name in rows]


def charges_csv(
    session: Session,
    *,
    award_id: int | None = None,
    work_from: str | None = None,
    work_to: str | None = None,
) -> str:
    """CSV of posted charges. Integer cents. Not a GL export (D36)."""
    stmt = (
        select(Charge, Award.short_code)
        .outerjoin(Award, Award.award_id == Charge.award_id)
        .order_by(Charge.charge_id)
    )
    if award_id is not None:
        stmt = stmt.where(Charge.award_id == award_id)
    if work_from:
        start = _iso_date(work_from, field="work_from")
        stmt = stmt.where(Charge.work_date >= start)
    if work_to:
        end = _iso_date(work_to, field="work_to")
        stmt = stmt.where(Charge.work_date <= end)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CHARGE_CSV_COLUMNS)
    for charge, short_code in session.execute(stmt).all():
        writer.writerow(
            [
                charge.charge_id,
                charge.source,
                charge.award_id,
                short_code or "",
                charge.category_code or "",
                charge.person_id if charge.person_id is not None else "",
                charge.work_date or "",
                charge.hours_hundredths if charge.hours_hundredths is not None else "",
                charge.amount_cents,
                charge.reverses_charge_id if charge.reverses_charge_id is not None else "",
                charge.created_at,
            ]
        )
    return buffer.getvalue()
