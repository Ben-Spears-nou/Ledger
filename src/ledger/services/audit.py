"""Append-only audit writes. Do not update or delete ``audit_event`` rows."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ledger.models import AuditEvent


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
