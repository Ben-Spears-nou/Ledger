"""Purchases, travel, commitments, and instruments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import Award, Commitment, Instrument, UserAccount
from ledger.schemas.commitments import (
    CommitmentOut,
    InstrumentIn,
    InstrumentOut,
    PurchaseIn,
    TravelIn,
)
from ledger.services.commitments import (
    CommitmentError,
    cancel_commitment,
    create_instrument,
    create_purchase,
    create_travel,
    list_commitments,
    list_instruments,
    post_commitment,
    post_instrument,
    serialize_commitment,
    serialize_instrument,
)

purchases_router = APIRouter(prefix="/purchases", tags=["commitments"])
travel_router = APIRouter(prefix="/travel", tags=["commitments"])
commitments_router = APIRouter(prefix="/commitments", tags=["commitments"])
instruments_router = APIRouter(prefix="/instruments", tags=["commitments"])
award_commitments_router = APIRouter(prefix="/awards", tags=["commitments"])


def _http(exc: CommitmentError) -> HTTPException:
    message = str(exc).lower()
    code = status.HTTP_400_BAD_REQUEST
    if "already" in message:
        code = status.HTTP_409_CONFLICT
    return HTTPException(code, str(exc))


@purchases_router.post("", response_model=CommitmentOut, status_code=status.HTTP_201_CREATED)
def post_purchase(
    payload: PurchaseIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> CommitmentOut:
    """Create an open purchase commitment (admin)."""
    try:
        row = create_purchase(session, payload, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_commitment(row)


@travel_router.post("", response_model=CommitmentOut, status_code=status.HTTP_201_CREATED)
def post_travel(
    payload: TravelIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> CommitmentOut:
    """Create an open travel commitment (admin)."""
    try:
        row = create_travel(session, payload, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_commitment(row)


@award_commitments_router.get("/{award_id}/commitments", response_model=list[CommitmentOut])
def get_award_commitments(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[CommitmentOut]:
    """List commitments for one award (admin)."""
    if session.get(Award, award_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    return [serialize_commitment(row) for row in list_commitments(session, award_id)]


@commitments_router.post("/{commitment_id}/post", response_model=CommitmentOut)
def post_one_commitment(
    commitment_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> CommitmentOut:
    """Post an open commitment as a charge (admin)."""
    row = session.get(Commitment, commitment_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "commitment not found")
    try:
        row = post_commitment(session, row, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_commitment(row)


@commitments_router.post("/{commitment_id}/cancel", response_model=CommitmentOut)
def cancel_one_commitment(
    commitment_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> CommitmentOut:
    """Cancel an open commitment (admin)."""
    row = session.get(Commitment, commitment_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "commitment not found")
    try:
        row = cancel_commitment(session, row, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_commitment(row)


@instruments_router.get("", response_model=list[InstrumentOut])
def get_instruments(
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[InstrumentOut]:
    """List instruments (admin)."""
    return [serialize_instrument(session, row) for row in list_instruments(session)]


@instruments_router.post("", response_model=InstrumentOut, status_code=status.HTTP_201_CREATED)
def post_new_instrument(
    payload: InstrumentIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> InstrumentOut:
    """Create an instrument and open share commitments (admin)."""
    try:
        row = create_instrument(session, payload, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_instrument(session, row)


@instruments_router.get("/{instrument_id}", response_model=InstrumentOut)
def get_instrument(
    instrument_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> InstrumentOut:
    """One instrument (admin)."""
    row = session.get(Instrument, instrument_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "instrument not found")
    return serialize_instrument(session, row)


@instruments_router.post("/{instrument_id}/post", response_model=InstrumentOut)
def post_one_instrument(
    instrument_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> InstrumentOut:
    """Post every open share commitment (admin)."""
    row = session.get(Instrument, instrument_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "instrument not found")
    try:
        row = post_instrument(session, row, actor_id=admin.user_account_id)
    except CommitmentError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_instrument(session, row)
