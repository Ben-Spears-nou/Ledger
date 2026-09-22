"""Admin home, staffing, search, funding expectations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import Award, FundingExpectation, UserAccount
from ledger.schemas.operations import (
    FundingExpectationIn,
    FundingExpectationOut,
    HomeOut,
    SearchOut,
    StaffingOut,
    StaffingScenarioIn,
    StaffingScenarioOut,
)
from ledger.services.operations import (
    OperationsError,
    add_funding_expectation,
    delete_funding_expectation,
    home_board,
    list_funding_expectations,
    search_ledger,
    serialize_funding,
    staffing_board,
    staffing_scenario,
)

home_router = APIRouter(prefix="/home", tags=["operations"])
staffing_router = APIRouter(prefix="/staffing", tags=["operations"])
search_router = APIRouter(prefix="/search", tags=["operations"])
funding_router = APIRouter(prefix="/awards", tags=["operations"])


def _http(exc: OperationsError) -> HTTPException:
    message = str(exc)
    if "not found" in message:
        return HTTPException(status.HTTP_404_NOT_FOUND, message)
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


@home_router.get("", response_model=HomeOut)
def get_home(
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> HomeOut:
    """This week's decisions: missing time, dues, aging, close, portfolio."""
    try:
        return home_board(session, as_of=as_of)
    except OperationsError as exc:
        raise _http(exc) from exc


@staffing_router.get("", response_model=StaffingOut)
def get_staffing(
    week_start: str | None = Query(default=None),
    weeks: int = Query(default=8, ge=1, le=12),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> StaffingOut:
    """Forward capacity vs assignments vs logged hours."""
    try:
        return staffing_board(session, week_start=week_start, weeks=weeks)
    except OperationsError as exc:
        raise _http(exc) from exc


@staffing_router.post("/scenario", response_model=StaffingScenarioOut)
def post_staffing_scenario(
    payload: StaffingScenarioIn,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> StaffingScenarioOut:
    """What-if loaded cost. Does not persist."""
    try:
        return staffing_scenario(session, payload)
    except OperationsError as exc:
        raise _http(exc) from exc


@search_router.get("", response_model=SearchOut)
def get_search(
    q: str = Query(min_length=1),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> SearchOut:
    """Find awards, people, CLINs, and documents."""
    try:
        return search_ledger(session, q)
    except OperationsError as exc:
        raise _http(exc) from exc


@funding_router.get("/{award_id}/funding-expectations", response_model=list[FundingExpectationOut])
def get_funding_expectations(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[FundingExpectationOut]:
    """Expected increments (not remaining)."""
    if session.get(Award, award_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    return list_funding_expectations(session, award_id)


@funding_router.post(
    "/{award_id}/funding-expectations",
    response_model=FundingExpectationOut,
    status_code=status.HTTP_201_CREATED,
)
def post_funding_expectation(
    award_id: int,
    payload: FundingExpectationIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> FundingExpectationOut:
    """Add an expected increment."""
    award = session.get(Award, award_id)
    if award is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    try:
        row = add_funding_expectation(session, award, payload, actor_id=admin.user_account_id)
    except OperationsError as exc:
        raise _http(exc) from exc
    return serialize_funding(row)


@funding_router.delete(
    "/{award_id}/funding-expectations/{expectation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_funding_expectation(
    award_id: int,
    expectation_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an expected increment."""
    award = session.get(Award, award_id)
    if award is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    row = session.get(FundingExpectation, expectation_id)
    if row is None or row.award_id != award.award_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "funding expectation not found")
    delete_funding_expectation(session, row, actor_id=admin.user_account_id)
