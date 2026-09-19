"""SOW work-plan CRUD, extraction, and progress-Gantt APIs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_current_user, get_db, require_admin
from ledger.models import UserAccount, WorkPlanItem
from ledger.schemas.work_plan import (
    WorkGanttOut,
    WorkPlanConfirmIn,
    WorkPlanDraftIn,
    WorkPlanItemOut,
    WorkPlanMoveIn,
    WorkPlanPatch,
    WorkPlanProposeIn,
    WorkPlanProposeOut,
)
from ledger.services.contract_schedule import ScheduleTrackError, require_award
from ledger.services.work_plan import (
    WorkPlanError,
    build_gantt,
    confirm,
    create_item,
    delete_item,
    list_items,
    move_item,
    patch_item,
    propose,
    serialize_item,
)

award_work_plan_router = APIRouter(prefix="/awards", tags=["work-plan"])
work_plan_router = APIRouter(prefix="/work-plan", tags=["work-plan"])
work_gantt_router = APIRouter(prefix="/work-gantt", tags=["work-plan"])


def _http(exc: ValueError) -> HTTPException:
    message = str(exc)
    code = status.HTTP_404_NOT_FOUND if "not found" in message else status.HTTP_400_BAD_REQUEST
    return HTTPException(code, message)


@award_work_plan_router.get("/{award_id}/work-plan", response_model=list[WorkPlanItemOut])
def get_award_work_plan(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[WorkPlanItemOut]:
    """Confirmed SOW requirements."""
    try:
        require_award(session, award_id)
    except ScheduleTrackError as exc:
        raise _http(exc) from exc
    return [serialize_item(row) for row in list_items(session, award_id)]


@award_work_plan_router.post(
    "/{award_id}/work-plan/propose",
    response_model=WorkPlanProposeOut,
)
def post_work_plan_propose(
    award_id: int,
    payload: WorkPlanProposeIn,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> WorkPlanProposeOut:
    """Extract a draft from numbered SOW requirements."""
    try:
        return propose(session, require_award(session, award_id), payload)
    except (ScheduleTrackError, WorkPlanError) as exc:
        raise _http(exc) from exc


@award_work_plan_router.post(
    "/{award_id}/work-plan/confirm",
    response_model=list[WorkPlanItemOut],
    status_code=status.HTTP_201_CREATED,
)
def post_work_plan_confirm(
    award_id: int,
    payload: WorkPlanConfirmIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> list[WorkPlanItemOut]:
    """Insert selected draft requirements."""
    try:
        rows = confirm(
            session,
            require_award(session, award_id),
            payload,
            actor_id=admin.user_account_id,
        )
    except (ScheduleTrackError, WorkPlanError) as exc:
        raise _http(exc) from exc
    return [serialize_item(row) for row in rows]


@award_work_plan_router.post(
    "/{award_id}/work-plan",
    response_model=WorkPlanItemOut,
    status_code=status.HTTP_201_CREATED,
)
def post_work_plan_item(
    award_id: int,
    payload: WorkPlanDraftIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WorkPlanItemOut:
    """Add one work-plan row."""
    try:
        row = create_item(
            session,
            require_award(session, award_id),
            payload,
            actor_id=admin.user_account_id,
        )
    except (ScheduleTrackError, WorkPlanError) as exc:
        raise _http(exc) from exc
    return serialize_item(row)


@work_plan_router.patch("/{item_id}", response_model=WorkPlanItemOut)
def patch_work_plan_item(
    item_id: int,
    payload: WorkPlanPatch,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WorkPlanItemOut:
    """Edit dates, title, ordering, notes, or percent complete."""
    row = session.get(WorkPlanItem, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "work-plan item not found")
    try:
        return serialize_item(patch_item(session, row, payload, actor_id=admin.user_account_id))
    except WorkPlanError as exc:
        raise _http(exc) from exc


@work_plan_router.post("/{item_id}/move", response_model=WorkPlanItemOut)
def post_work_plan_move(
    item_id: int,
    payload: WorkPlanMoveIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> WorkPlanItemOut:
    """Move a requirement one place up or down. Dates are unchanged."""
    row = session.get(WorkPlanItem, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "work-plan item not found")
    return serialize_item(move_item(session, row, payload, actor_id=admin.user_account_id))


@work_plan_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_plan_item(
    item_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete one work-plan row."""
    row = session.get(WorkPlanItem, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "work-plan item not found")
    delete_item(session, row, actor_id=admin.user_account_id)


@work_gantt_router.get("", response_model=WorkGanttOut)
def get_work_gantt(
    award_id: int | None = Query(default=None),
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> WorkGanttOut:
    """Portfolio or award work-progress Gantt."""
    try:
        return build_gantt(
            session,
            award_id=award_id,
            as_of=date.fromisoformat(as_of) if as_of else None,
        )
    except ValueError as exc:
        raise _http(WorkPlanError("as_of must be YYYY-MM-DD")) from exc


@award_work_plan_router.get("/{award_id}/work-gantt", response_model=WorkGanttOut)
def get_award_work_gantt(
    award_id: int,
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> WorkGanttOut:
    """One award's work-progress Gantt."""
    try:
        return build_gantt(
            session,
            award_id=award_id,
            as_of=date.fromisoformat(as_of) if as_of else None,
        )
    except ValueError as exc:
        raise _http(WorkPlanError("as_of must be YYYY-MM-DD")) from exc
