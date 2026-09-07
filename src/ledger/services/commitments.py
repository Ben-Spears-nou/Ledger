"""Purchases, travel, instrument splits, and posting to charge (Phase 4)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.db.seed import get_default_organization_id
from ledger.models import (
    Award,
    BudgetCategory,
    BudgetLine,
    Charge,
    Commitment,
    Instrument,
    InstrumentShare,
    Person,
)
from ledger.schemas.commitments import (
    CommitmentOut,
    CommitmentPatch,
    InstrumentIn,
    InstrumentOut,
    InstrumentShareOut,
    PurchaseIn,
    TravelIn,
)
from ledger.services.audit import record_event
from ledger.services.awards import active_budget_version, remaining_for


class CommitmentError(ValueError):
    """Domain error turned into HTTP 400/409 by the API."""


SHARE_TOTAL = 10_000


def split_cents(amount_cents: int, shares: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Allocate ``amount_cents`` by ``share_pct``. Last share takes the remainder (D27)."""
    if not shares:
        raise CommitmentError("at least one share is required")
    total_pct = sum(pct for _, pct in shares)
    if total_pct != SHARE_TOTAL:
        raise CommitmentError("share_pct values must sum to 10000 (100%)")
    result: list[tuple[int, int]] = []
    allocated = 0
    last = len(shares) - 1
    for index, (award_id, pct) in enumerate(shares):
        cents = amount_cents - allocated if index == last else amount_cents * pct // SHARE_TOTAL
        allocated += cents
        result.append((award_id, cents))
    return result


def serialize_commitment(row: Commitment) -> CommitmentOut:
    """API representation of one commitment."""
    return CommitmentOut(
        commitment_id=row.commitment_id,
        award_id=row.award_id,
        kind=row.kind,
        status_code=row.status_code,
        category_code=row.category_code,
        amount_cents=row.amount_cents,
        description=row.description,
        vendor=row.vendor,
        person_id=row.person_id,
        effective_date=row.effective_date,
        trip_end=row.trip_end,
        expected_date=row.expected_date,
        instrument_id=row.instrument_id,
        charge_id=row.charge_id,
    )


def serialize_instrument(session: Session, row: Instrument) -> InstrumentOut:
    """Instrument plus shares and child commitments."""
    shares = session.scalars(
        select(InstrumentShare)
        .where(InstrumentShare.instrument_id == row.instrument_id)
        .order_by(InstrumentShare.instrument_share_id)
    ).all()
    cents_by_award = {
        award_id: cents
        for award_id, cents in split_cents(
            row.amount_cents, [(share.award_id, share.share_pct) for share in shares]
        )
    }
    commitments = session.scalars(
        select(Commitment)
        .where(Commitment.instrument_id == row.instrument_id)
        .order_by(Commitment.commitment_id)
    ).all()
    return InstrumentOut(
        instrument_id=row.instrument_id,
        short_code=row.short_code,
        title=row.title,
        amount_cents=row.amount_cents,
        category_code=row.category_code,
        status_code=row.status_code,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        shares=[
            InstrumentShareOut(
                instrument_share_id=share.instrument_share_id,
                award_id=share.award_id,
                share_pct=share.share_pct,
                amount_cents=cents_by_award.get(share.award_id, 0),
            )
            for share in shares
        ],
        commitments=[serialize_commitment(item) for item in commitments],
    )


def _require_award(session: Session, award_id: int) -> Award:
    award = session.get(Award, award_id)
    if award is None:
        raise CommitmentError("award not found")
    if award.status_code == "closed":
        raise CommitmentError("cannot commit against a closed award")
    if award.status_code == "pipeline":
        raise CommitmentError("cannot commit against a pipeline award")
    return award


def _require_category(session: Session, code: str) -> None:
    if session.get(BudgetCategory, code) is None:
        raise CommitmentError(f"unknown category_code: {code}")


def _guard_remaining_approved(session: Session, award: Award, amount_cents: int) -> None:
    if not award.enforce_ceiling:
        return
    remaining = remaining_for(session, award.award_id)
    if remaining is None:
        return
    if remaining.remaining_approved_cents - amount_cents < 0:
        raise CommitmentError(
            f"{award.short_code} would exceed approved remaining "
            f"({remaining.remaining_approved_cents} cents)"
        )


def _labor_line_for_category(
    session: Session, award_id: int, category_code: str
) -> BudgetLine | None:
    version = active_budget_version(session, award_id)
    if version is None:
        return None
    return session.scalar(
        select(BudgetLine)
        .where(
            BudgetLine.budget_version_id == version.budget_version_id,
            BudgetLine.category_code == category_code,
        )
        .order_by(BudgetLine.sort_order, BudgetLine.budget_line_id)
    )


def _add_commitment(
    session: Session,
    *,
    award: Award,
    kind: str,
    category_code: str,
    amount_cents: int,
    description: str | None,
    vendor: str | None,
    person_id: int | None,
    effective_date: str,
    trip_end: str | None,
    expected_date: str | None,
    instrument_id: int | None,
    actor_id: int | None,
) -> Commitment:
    _require_category(session, category_code)
    _guard_remaining_approved(session, award, amount_cents)
    if person_id is not None and session.get(Person, person_id) is None:
        raise CommitmentError("person not found")
    row = Commitment(
        award_id=award.award_id,
        kind=kind,
        status_code="open",
        category_code=category_code,
        amount_cents=amount_cents,
        description=description,
        vendor=vendor,
        person_id=person_id,
        effective_date=effective_date,
        trip_end=trip_end,
        expected_date=expected_date,
        instrument_id=instrument_id,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="commitment_create",
        entity_type="commitment",
        entity_id=row.commitment_id,
        actor_user_id=actor_id,
        detail={"kind": kind, "award_id": award.award_id, "amount_cents": amount_cents},
    )
    return row


def create_purchase(session: Session, payload: PurchaseIn, *, actor_id: int | None) -> Commitment:
    """Insert an open purchase commitment."""
    award = _require_award(session, payload.award_id)
    return _add_commitment(
        session,
        award=award,
        kind="purchase",
        category_code=payload.category_code.strip(),
        amount_cents=payload.amount_cents,
        description=payload.description,
        vendor=payload.vendor,
        person_id=None,
        effective_date=payload.effective_date,
        trip_end=None,
        expected_date=payload.expected_date,
        instrument_id=None,
        actor_id=actor_id,
    )


def create_travel(session: Session, payload: TravelIn, *, actor_id: int | None) -> Commitment:
    """Insert an open travel commitment."""
    award = _require_award(session, payload.award_id)
    category = (payload.category_code or "travel").strip()
    return _add_commitment(
        session,
        award=award,
        kind="travel",
        category_code=category,
        amount_cents=payload.amount_cents,
        description=payload.description,
        vendor=None,
        person_id=payload.person_id,
        effective_date=payload.effective_date,
        trip_end=payload.trip_end,
        expected_date=payload.expected_date,
        instrument_id=None,
        actor_id=actor_id,
    )


def list_commitments(session: Session, award_id: int | None = None) -> list[Commitment]:
    """Commitments, newest last."""
    stmt = select(Commitment).order_by(Commitment.commitment_id)
    if award_id is not None:
        stmt = stmt.where(Commitment.award_id == award_id)
    return list(session.scalars(stmt))


def post_commitment(session: Session, row: Commitment, *, actor_id: int | None) -> Commitment:
    """Turn an open commitment into a charge (D25)."""
    if row.status_code == "posted":
        raise CommitmentError("commitment is already posted")
    if row.status_code != "open":
        raise CommitmentError("only open commitments can be posted")
    award = session.get(Award, row.award_id)
    if award is None:
        raise CommitmentError("award not found")
    if award.enforce_ceiling:
        remaining = remaining_for(session, award.award_id)
        if remaining is not None and remaining.remaining_funded_cents - row.amount_cents < 0:
            raise CommitmentError(
                f"{award.short_code} would exceed funded remaining "
                f"({remaining.remaining_funded_cents} cents)"
            )
    line = _labor_line_for_category(session, row.award_id, row.category_code)
    charge = Charge(
        source=row.kind,
        award_id=row.award_id,
        budget_line_id=line.budget_line_id if line else None,
        category_code=row.category_code,
        person_id=row.person_id,
        work_date=row.effective_date,
        amount_cents=row.amount_cents,
        created_by=actor_id,
    )
    session.add(charge)
    session.flush()
    row.charge_id = charge.charge_id
    row.status_code = "posted"
    session.flush()
    record_event(
        session,
        action="commitment_post",
        entity_type="commitment",
        entity_id=row.commitment_id,
        actor_user_id=actor_id,
        detail={"charge_id": charge.charge_id, "amount_cents": row.amount_cents},
    )
    return row


def patch_commitment(
    session: Session, row: Commitment, payload: CommitmentPatch, *, actor_id: int | None
) -> Commitment:
    """Set expected invoice date. Does not change remaining."""
    data = payload.model_dump(exclude_unset=True)
    if "expected_date" in data:
        value = data["expected_date"]
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise CommitmentError("expected_date must be YYYY-MM-DD") from exc
        row.expected_date = value or None
    if "description" in data:
        row.description = data["description"]
    session.flush()
    record_event(
        session,
        action="commitment_update",
        entity_type="commitment",
        entity_id=row.commitment_id,
        actor_user_id=actor_id,
        detail={"award_id": row.award_id},
    )
    return row


def cancel_commitment(session: Session, row: Commitment, *, actor_id: int | None) -> Commitment:
    """Drop an open commitment from remaining. Does not insert a charge."""
    if row.status_code != "open":
        raise CommitmentError("only open commitments can be cancelled")
    row.status_code = "cancelled"
    session.flush()
    record_event(
        session,
        action="commitment_cancel",
        entity_type="commitment",
        entity_id=row.commitment_id,
        actor_user_id=actor_id,
        detail={"award_id": row.award_id},
    )
    return row


def create_instrument(
    session: Session, payload: InstrumentIn, *, actor_id: int | None
) -> Instrument:
    """Insert an instrument, shares, and one open commitment per share."""
    short = payload.short_code.strip()
    title = payload.title.strip()
    if not short or not title:
        raise CommitmentError("short_code and title are required")
    _require_category(session, payload.category_code.strip())
    pairs: list[tuple[int, int]] = []
    seen: set[int] = set()
    for share in payload.shares:
        if share.award_id in seen:
            raise CommitmentError("each award may appear only once on an instrument")
        seen.add(share.award_id)
        _require_award(session, share.award_id)
        pairs.append((share.award_id, share.share_pct))
    allocations = split_cents(payload.amount_cents, pairs)
    org_id = get_default_organization_id(session)
    clash = session.scalar(
        select(Instrument).where(
            Instrument.organization_id == org_id, Instrument.short_code == short
        )
    )
    if clash is not None:
        raise CommitmentError("instrument short_code already exists")
    row = Instrument(
        organization_id=org_id,
        short_code=short,
        title=title,
        amount_cents=payload.amount_cents,
        category_code=payload.category_code.strip(),
        status_code="open",
        effective_from=payload.effective_from,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    for award_id, pct in pairs:
        session.add(
            InstrumentShare(instrument_id=row.instrument_id, award_id=award_id, share_pct=pct)
        )
    session.flush()
    for award_id, cents in allocations:
        award = _require_award(session, award_id)
        _add_commitment(
            session,
            award=award,
            kind="instrument",
            category_code=row.category_code,
            amount_cents=cents,
            description=title,
            vendor=None,
            person_id=None,
            effective_date=payload.effective_from,
            trip_end=None,
            expected_date=None,
            instrument_id=row.instrument_id,
            actor_id=actor_id,
        )
    record_event(
        session,
        action="instrument_create",
        entity_type="instrument",
        entity_id=row.instrument_id,
        actor_user_id=actor_id,
        detail={"short_code": short, "amount_cents": payload.amount_cents},
    )
    return row


def list_instruments(session: Session) -> list[Instrument]:
    """All instruments, newest last."""
    return list(session.scalars(select(Instrument).order_by(Instrument.instrument_id)))


def post_instrument(session: Session, row: Instrument, *, actor_id: int | None) -> Instrument:
    """Post every still-open share commitment."""
    if row.status_code == "posted":
        raise CommitmentError("instrument is already posted")
    if row.status_code != "open":
        raise CommitmentError("only open instruments can be posted")
    children = session.scalars(
        select(Commitment).where(Commitment.instrument_id == row.instrument_id)
    ).all()
    for child in children:
        if child.status_code == "open":
            post_commitment(session, child, actor_id=actor_id)
        elif child.status_code != "posted":
            raise CommitmentError("cannot post an instrument with cancelled shares")
    row.status_code = "posted"
    session.flush()
    return row


def delete_instrument(session: Session, row: Instrument, *, actor_id: int | None) -> None:
    """Remove an unposted instrument and its open share commitments (D45)."""
    children = list(
        session.scalars(select(Commitment).where(Commitment.instrument_id == row.instrument_id))
    )
    if any(child.status_code == "posted" for child in children):
        raise CommitmentError("cannot delete an instrument that has posted shares")
    instrument_id = row.instrument_id
    short = row.short_code
    for child in children:
        session.delete(child)
    session.flush()
    shares = list(
        session.scalars(
            select(InstrumentShare).where(InstrumentShare.instrument_id == instrument_id)
        )
    )
    for share in shares:
        session.delete(share)
    session.flush()
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="instrument_delete",
        entity_type="instrument",
        entity_id=instrument_id,
        actor_user_id=actor_id,
        detail={"short_code": short},
    )
