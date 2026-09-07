"""Award intake, mods, rate-policy revisions, and remaining."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import get_current_user, get_db, require_admin
from ledger.models import Award, AwardRatePolicy, Clin, UserAccount
from ledger.schemas.awards import (
    AwardCardOut,
    AwardCreate,
    AwardModCreate,
    AwardOut,
    AwardRemainingOut,
    AwardUpdate,
    ClinExerciseIn,
    ClinIn,
    ClinOut,
    ClinUpdate,
    RatePolicyIn,
    RatePolicyOut,
)
from ledger.services.awards import (
    AwardError,
    add_clin,
    apply_mod,
    create_award,
    delete_award,
    delete_clin,
    delete_rate_policy,
    exercise_clin,
    remaining_for,
    revise_rate_policy,
    serialize_award,
    serialize_award_card,
    serialize_clin,
    serialize_policy,
    update_award,
    update_clin,
)

router = APIRouter(prefix="/awards", tags=["awards"])


def _http(exc: AwardError) -> HTTPException:
    message = str(exc)
    if "posted activity" in message or "cannot delete" in message:
        return HTTPException(status.HTTP_409_CONFLICT, message)
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


def _get_award(session: Session, award_id: int) -> Award:
    award = session.get(Award, award_id)
    if award is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    return award


def _get_clin(session: Session, award: Award, clin_id: int) -> Clin:
    row = session.get(Clin, clin_id)
    if row is None or row.award_id != award.award_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "clin not found")
    return row


@router.get("")
def list_awards(
    as_: str | None = Query(default=None, alias="as"),
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> list[AwardOut] | list[AwardCardOut]:
    """List awards. Employees (and ``?as=picker``) get the slim DTO (D18)."""
    awards = session.scalars(select(Award).order_by(Award.short_code)).all()
    if user.role_code != "admin" or as_ == "picker":
        return [serialize_award_card(award) for award in awards]
    return [serialize_award(session, award) for award in awards]


@router.post("", response_model=AwardOut, status_code=status.HTTP_201_CREATED)
def post_award(
    payload: AwardCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> AwardOut:
    """Create an award with rate policy and budget (admin)."""
    try:
        award = create_award(session, payload, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.flush()
    return serialize_award(session, award)


@router.get("/{award_id}")
def get_award(
    award_id: int,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> AwardOut | AwardCardOut:
    """Admin gets AwardOut; employees get the slim charge-code card (D18)."""
    award = _get_award(session, award_id)
    if user.role_code != "admin":
        return serialize_award_card(award)
    return serialize_award(session, award)


@router.patch("/{award_id}", response_model=AwardOut)
def patch_award(
    award_id: int,
    payload: AwardUpdate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> AwardOut:
    """Patch header fields (admin)."""
    try:
        award = update_award(
            session, _get_award(session, award_id), payload, actor_id=admin.user_account_id
        )
    except AwardError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_award(session, award)


@router.delete("/{award_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_award(
    award_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an unused award (D39). Used awards must be closed."""
    award = _get_award(session, award_id)
    try:
        delete_award(session, award, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise _http(exc) from exc


@router.post("/{award_id}/clins", response_model=ClinOut, status_code=status.HTTP_201_CREATED)
def post_clin(
    award_id: int,
    payload: ClinIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ClinOut:
    """Add a CLIN or option line."""
    award = _get_award(session, award_id)
    try:
        row = add_clin(session, award, payload, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise _http(exc) from exc
    return serialize_clin(row)


@router.patch("/{award_id}/clins/{clin_id}", response_model=ClinOut)
def patch_clin(
    award_id: int,
    clin_id: int,
    payload: ClinUpdate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ClinOut:
    """Patch a CLIN (not exercise)."""
    award = _get_award(session, award_id)
    clin = _get_clin(session, award, clin_id)
    try:
        row = update_clin(session, award, clin, payload, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise _http(exc) from exc
    return serialize_clin(row)


@router.post("/{award_id}/clins/{clin_id}/exercise", response_model=ClinOut)
def post_clin_exercise(
    award_id: int,
    clin_id: int,
    payload: ClinExerciseIn | None = None,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ClinOut:
    """Mark an option CLIN exercised."""
    award = _get_award(session, award_id)
    clin = _get_clin(session, award, clin_id)
    try:
        row = exercise_clin(
            session, award, clin, payload or ClinExerciseIn(), actor_id=admin.user_account_id
        )
    except AwardError as exc:
        raise _http(exc) from exc
    return serialize_clin(row)


@router.delete("/{award_id}/clins/{clin_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_clin(
    award_id: int,
    clin_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an unexercised CLIN."""
    award = _get_award(session, award_id)
    clin = _get_clin(session, award, clin_id)
    try:
        delete_clin(session, award, clin, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise _http(exc) from exc


@router.post("/{award_id}/mods", response_model=AwardOut, status_code=status.HTTP_201_CREATED)
def post_mod(
    award_id: int,
    payload: AwardModCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> AwardOut:
    """Apply a modification (admin)."""
    award = _get_award(session, award_id)
    try:
        apply_mod(session, award, payload, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.flush()
    return serialize_award(session, award)


@router.post(
    "/{award_id}/rate-policies",
    response_model=RatePolicyOut,
    status_code=status.HTTP_201_CREATED,
)
def post_rate_policy(
    award_id: int,
    payload: RatePolicyIn,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> RatePolicyOut:
    """Insert a new dated rate policy; close the previous row (admin)."""
    award = _get_award(session, award_id)
    try:
        policy = revise_rate_policy(session, award, payload, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.flush()
    return serialize_policy(session, policy)


@router.delete(
    "/{award_id}/rate-policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_rate_policy(
    award_id: int,
    policy_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an unused rate-policy revision (D45)."""
    _get_award(session, award_id)
    policy = session.get(AwardRatePolicy, policy_id)
    if policy is None or policy.award_id != award_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rate policy not found")
    try:
        delete_rate_policy(session, policy, actor_id=admin.user_account_id)
    except AwardError as exc:
        raise _http(exc) from exc


@router.get("/{award_id}/remaining", response_model=AwardRemainingOut)
def get_remaining(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> AwardRemainingOut:
    """Return ``v_budget_remaining`` for one award."""
    _get_award(session, award_id)
    remaining = remaining_for(session, award_id)
    if remaining is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "remaining view has no row")
    return remaining
