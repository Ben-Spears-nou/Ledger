"""Admin pipeline forecast, burn, and computed alerts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import UserAccount
from ledger.models.pipeline import PipelineNode
from ledger.schemas.pipeline import (
    AlertOut,
    AwardBurnOut,
    PipelineCreate,
    PipelineOut,
    PipelinePatch,
)
from ledger.services.burn import BurnError, award_burn, list_alerts
from ledger.services.pipeline import (
    PipelineError,
    create_pipeline,
    delete_pipeline,
    list_pipeline,
    patch_pipeline,
    require_award,
    serialize_pipeline,
)

award_pipeline_router = APIRouter(prefix="/awards", tags=["pipeline"])
pipeline_router = APIRouter(prefix="/pipeline", tags=["pipeline"])
award_burn_router = APIRouter(prefix="/awards", tags=["burn"])
alerts_router = APIRouter(prefix="/alerts", tags=["alerts"])


def _http(exc: PipelineError | BurnError, *, not_found: bool = False) -> HTTPException:
    message = str(exc)
    missing = {"award not found", "pipeline node not found"}
    if not_found or message in missing:
        return HTTPException(status.HTTP_404_NOT_FOUND, message)
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


@award_pipeline_router.get("/{award_id}/pipeline", response_model=list[PipelineOut])
def get_award_pipeline(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[PipelineOut]:
    """Forecast nodes on one award."""
    try:
        award = require_award(session, award_id)
    except PipelineError as exc:
        raise _http(exc, not_found=True) from exc
    return [
        serialize_pipeline(row, award) for row, _joined in list_pipeline(session, award_id=award_id)
    ]


@award_pipeline_router.post(
    "/{award_id}/pipeline",
    response_model=PipelineOut,
    status_code=status.HTTP_201_CREATED,
)
def post_award_pipeline(
    award_id: int,
    payload: PipelineCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> PipelineOut:
    """Add a forecast node."""
    try:
        award = require_award(session, award_id)
        row = create_pipeline(session, award, payload, actor_id=admin.user_account_id)
    except PipelineError as exc:
        raise _http(exc, not_found=str(exc) == "award not found") from exc
    return serialize_pipeline(row, award)


@pipeline_router.get("", response_model=list[PipelineOut])
def get_pipeline(
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[PipelineOut]:
    """Forecast nodes across awards."""
    return [serialize_pipeline(row, award) for row, award in list_pipeline(session)]


@pipeline_router.patch("/{pipeline_node_id}", response_model=PipelineOut)
def patch_pipeline_item(
    pipeline_node_id: int,
    payload: PipelinePatch,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> PipelineOut:
    """Edit a forecast node."""
    row = session.get(PipelineNode, pipeline_node_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline node not found")
    try:
        row = patch_pipeline(session, row, payload, actor_id=admin.user_account_id)
        award = require_award(session, row.award_id)
    except PipelineError as exc:
        raise _http(exc) from exc
    return serialize_pipeline(row, award)


@pipeline_router.delete("/{pipeline_node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_item(
    pipeline_node_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Remove a forecast node."""
    row = session.get(PipelineNode, pipeline_node_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline node not found")
    delete_pipeline(session, row, actor_id=admin.user_account_id)


@award_burn_router.get("/{award_id}/burn", response_model=AwardBurnOut)
def get_award_burn(
    award_id: int,
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> AwardBurnOut:
    """Monthly actuals, EAC, and runway."""
    try:
        award = require_award(session, award_id)
        return award_burn(session, award, as_of=as_of)
    except (PipelineError, BurnError) as exc:
        raise _http(exc, not_found=str(exc) == "award not found") from exc


@alerts_router.get("", response_model=list[AlertOut])
def get_alerts(
    as_of: str | None = Query(default=None),
    award_id: int | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[AlertOut]:
    """Computed 75% and PoP warnings (D34)."""
    try:
        return list_alerts(session, as_of=as_of, award_id=award_id)
    except BurnError as exc:
        raise _http(exc) from exc
