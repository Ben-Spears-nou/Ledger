"""Admin-only audit list and charges CSV (D19, D35–D36)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import UserAccount
from ledger.services.audit import AuditError, charges_csv, list_audit_events

router = APIRouter(prefix="/admin", tags=["admin"])


def _http(exc: AuditError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/audit")
def list_audit(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    occurred_from: str | None = Query(default=None),
    occurred_to: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[dict[str, object]]:
    """Audit events, newest first. Filters are optional (D35)."""
    try:
        return list_audit_events(
            session,
            action=action,
            entity_type=entity_type,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
        )
    except AuditError as exc:
        raise _http(exc) from exc


@router.get("/charges.csv")
def get_charges_csv(
    award_id: int | None = Query(default=None),
    work_from: str | None = Query(default=None),
    work_to: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> Response:
    """Convenience dump of posted charges. Not the books (D36)."""
    try:
        body = charges_csv(session, award_id=award_id, work_from=work_from, work_to=work_to)
    except AuditError as exc:
        raise _http(exc) from exc
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ledger-charges.csv"'},
    )
