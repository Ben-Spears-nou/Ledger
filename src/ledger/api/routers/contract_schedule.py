"""Glossary, contract schedule, and Gantt APIs (Phase 12)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_current_user, get_db, require_admin
from ledger.models import UserAccount
from ledger.models.contract_schedule import ScheduleItem
from ledger.schemas.contract_schedule import (
    GanttOut,
    GlossaryTermOut,
    ScheduleConfirmIn,
    ScheduleDraftIn,
    ScheduleItemOut,
    SchedulePatch,
    ScheduleProposeIn,
    ScheduleProposeOut,
)
from ledger.services.contract_schedule import (
    ScheduleTrackError,
    build_gantt,
    confirm_schedule,
    create_schedule_item,
    delete_schedule_item,
    list_schedule,
    patch_schedule_item,
    propose_schedule,
    require_award,
    serialize_item,
)
from ledger.services.glossary import list_glossary

glossary_router = APIRouter(prefix="/glossary", tags=["glossary"])
gantt_router = APIRouter(prefix="/gantt", tags=["gantt"])
award_schedule_router = APIRouter(prefix="/awards", tags=["schedule"])
schedule_items_router = APIRouter(prefix="/schedule", tags=["schedule"])


def _http(exc: ScheduleTrackError) -> HTTPException:
    message = str(exc)
    if "not found" in message:
        return HTTPException(status.HTTP_404_NOT_FOUND, message)
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


@glossary_router.get("", response_model=list[GlossaryTermOut])
def get_glossary(
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> list[GlossaryTermOut]:
    """Common language. Any logged-in user."""
    return list_glossary(session)


@gantt_router.get("", response_model=GanttOut)
def get_gantt(
    award_id: int | None = Query(default=None),
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> GanttOut:
    """Computed Gantt for one award or the portfolio."""
    try:
        as_of_date = date.fromisoformat(as_of) if as_of else None
        return build_gantt(session, award_id=award_id, as_of=as_of_date)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "as_of must be YYYY-MM-DD") from exc
    except ScheduleTrackError as exc:
        raise _http(exc) from exc


@award_schedule_router.get("/{award_id}/gantt", response_model=GanttOut)
def get_award_gantt(
    award_id: int,
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> GanttOut:
    """Gantt for one award."""
    try:
        as_of_date = date.fromisoformat(as_of) if as_of else None
        return build_gantt(session, award_id=award_id, as_of=as_of_date)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "as_of must be YYYY-MM-DD") from exc
    except ScheduleTrackError as exc:
        raise _http(exc) from exc


@award_schedule_router.get("/{award_id}/schedule", response_model=list[ScheduleItemOut])
def get_award_schedule(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[ScheduleItemOut]:
    """Confirmed schedule rows."""
    try:
        require_award(session, award_id)
    except ScheduleTrackError as exc:
        raise _http(exc) from exc
    return [serialize_item(row) for row in list_schedule(session, award_id)]


@award_schedule_router.post("/{award_id}/schedule/propose", response_model=ScheduleProposeOut)
def post_schedule_propose(
    award_id: int,
    payload: ScheduleProposeIn,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> ScheduleProposeOut:
    """Draft only; confirm to save."""
    try:
        award = require_award(session, award_id)
        return propose_schedule(session, award, payload)
    except ScheduleTrackError as exc:
        raise _http(exc) from exc


@award_schedule_router.post(
    "/{award_id}/schedule/confirm",
    response_model=list[ScheduleItemOut],
    status_code=status.HTTP_201_CREATED,
)
def post_schedule_confirm(
    award_id: int,
    payload: ScheduleConfirmIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> list[ScheduleItemOut]:
    """Insert the rows the operator kept."""
    try:
        award = require_award(session, award_id)
        rows = confirm_schedule(session, award, payload, actor_id=admin.user_account_id)
    except ScheduleTrackError as extra:
        raise _http(extra) from extra
    return [serialize_item(row) for row in rows]


@award_schedule_router.post(
    "/{award_id}/schedule",
    response_model=ScheduleItemOut,
    status_code=status.HTTP_201_CREATED,
)
def post_schedule_item(
    award_id: int,
    payload: ScheduleDraftIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ScheduleItemOut:
    """Manual add without propose."""
    try:
        award = require_award(session, award_id)
        row = create_schedule_item(session, award, payload, actor_id=admin.user_account_id)
    except ScheduleTrackError as extra:
        raise _http(extra) from extra
    return serialize_item(row)


@schedule_items_router.patch("/{item_id}", response_model=ScheduleItemOut)
def patch_item(
    item_id: int,
    payload: SchedulePatch,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ScheduleItemOut:
    """Edit a confirmed row."""
    row = session.get(ScheduleItem, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule item not found")
    try:
        patched = patch_schedule_item(session, row, payload, actor_id=admin.user_account_id)
    except ScheduleTrackError as extra:
        raise _http(extra) from extra
    return serialize_item(patched)


@schedule_items_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Remove a schedule row."""
    row = session.get(ScheduleItem, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule item not found")
    delete_schedule_item(session, row, actor_id=admin.user_account_id)
