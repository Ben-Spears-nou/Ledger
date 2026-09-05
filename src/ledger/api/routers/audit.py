"""Admin-only audit list. Phase 7 is the real UI/CSV (D19)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import AuditEvent, UserAccount

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit")
def list_audit(
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[dict[str, object]]:
    """Plain JSON list of audit events, newest first."""
    rows = session.scalars(select(AuditEvent).order_by(AuditEvent.audit_event_id.desc())).all()
    result: list[dict[str, object]] = []
    for row in rows:
        detail: object = None
        if row.detail:
            try:
                detail = json.loads(row.detail)
            except json.JSONDecodeError:
                detail = row.detail
        result.append(
            {
                "audit_event_id": row.audit_event_id,
                "occurred_at": row.occurred_at,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "detail": detail,
            }
        )
    return result
