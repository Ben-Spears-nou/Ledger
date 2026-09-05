"""Create and revise awards, rate policies, and budget versions."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ledger.db.seed import get_default_organization_id
from ledger.models import (
    Agency,
    Award,
    AwardMod,
    AwardRateOverride,
    AwardRatePolicy,
    AwardType,
    BudgetLine,
    BudgetTemplateLine,
    BudgetVersion,
    Clin,
    RatePolicyTemplate,
)
from ledger.schemas.awards import (
    AwardCardOut,
    AwardCreate,
    AwardModCreate,
    AwardOut,
    AwardRemainingOut,
    AwardUpdate,
    BudgetLineChange,
    BudgetLineIn,
    BudgetLineOut,
    ClinIn,
    ClinOut,
    RateOverrideOut,
    RatePolicyIn,
    RatePolicyOut,
)
from ledger.services.audit import record_event


class AwardError(ValueError):
    """Domain error turned into an HTTP 400 by the API."""


def _as_int_flag(value: bool | int) -> int:
    return 1 if value else 0


def record_agency(session: Session, name: str) -> None:
    """Insert ``name`` into the growing agency lookup (D1)."""
    trimmed = name.strip()
    if not trimmed:
        raise AwardError("agency is required")
    if session.get(Agency, trimmed) is None:
        session.add(Agency(agency_name=trimmed))


def _template(session: Session, code: str | None) -> RatePolicyTemplate | None:
    if not code:
        return None
    row = session.get(RatePolicyTemplate, code)
    if row is None:
        raise AwardError(f"unknown rate policy template: {code}")
    return row


def _resolve_policy_fields(session: Session, incoming: RatePolicyIn) -> dict[str, object]:
    """Merge a template (if any) with explicit fields. Explicit wins."""
    template = _template(session, incoming.template_code)
    cost_basis = incoming.cost_basis_code or (template.cost_basis_code if template else None)
    if not cost_basis:
        raise AwardError("rate_policy.cost_basis_code is required (or pick a template)")

    def pick(explicit: int | None, attr: str) -> int:
        if explicit is not None:
            return explicit
        return int(getattr(template, attr)) if template is not None else 0

    fee_in_burden = incoming.fee_in_burden
    if fee_in_burden is None:
        fee_in_burden = bool(template.fee_in_burden) if template is not None else False

    return {
        "cost_basis_code": cost_basis,
        "fringe_pct": pick(incoming.fringe_pct, "fringe_pct"),
        "oh_pct": pick(incoming.oh_pct, "oh_pct"),
        "ga_pct": pick(incoming.ga_pct, "ga_pct"),
        "fee_pct": pick(incoming.fee_pct, "fee_pct"),
        "fee_in_burden": _as_int_flag(fee_in_burden),
    }


def _default_budget_lines(session: Session, type_code: str) -> list[BudgetLineIn]:
    rows = session.scalars(
        select(BudgetTemplateLine)
        .where(BudgetTemplateLine.award_type_code == type_code)
        .order_by(BudgetTemplateLine.sort_order)
    ).all()
    if not rows:
        raise AwardError(f"no budget template lines for award type {type_code}")
    return [
        BudgetLineIn(
            category_code=row.category_code,
            label=row.label,
            approved_cents=0,
            sort_order=row.sort_order,
        )
        for row in rows
    ]


def _add_overrides(session: Session, policy: AwardRatePolicy, incoming: RatePolicyIn) -> None:
    for item in incoming.overrides:
        if (item.person_id is None) == (item.labor_category is None):
            raise AwardError("each override needs exactly one of person_id or labor_category")
        session.add(
            AwardRateOverride(
                policy_id=policy.policy_id,
                person_id=item.person_id,
                labor_category=item.labor_category,
                loaded_rate_cents=item.loaded_rate_cents,
            )
        )


def _personnel_line_id(lines: list[BudgetLine]) -> int | None:
    for line in lines:
        if line.category_code == "personnel":
            return line.budget_line_id
    return lines[0].budget_line_id if lines else None


def _close_open_policies(session: Session, award_id: int, new_from: str) -> None:
    """Set effective_to on the open policy. Does not update in place (D5)."""
    open_rows = session.scalars(
        select(AwardRatePolicy).where(
            AwardRatePolicy.award_id == award_id,
            AwardRatePolicy.effective_to.is_(None),
        )
    ).all()
    closed_on = _day_before(new_from)
    for row in open_rows:
        row.effective_to = closed_on if closed_on >= row.effective_from else new_from


def _day_before(iso_date: str) -> str:
    parsed = date.fromisoformat(iso_date)
    return (parsed - timedelta(days=1)).isoformat()


def create_award(session: Session, payload: AwardCreate, *, actor_id: int | None) -> Award:
    """Insert an award, active budget, and first rate policy."""
    award_type = session.get(AwardType, payload.type_code)
    if award_type is None:
        raise AwardError(f"unknown award type: {payload.type_code}")

    record_agency(session, payload.agency)
    org_id = get_default_organization_id(session)

    award = Award(
        organization_id=org_id,
        short_code=payload.short_code.strip(),
        title=payload.title.strip(),
        agency=payload.agency.strip(),
        instrument_code=payload.instrument_code,
        mechanism_code=payload.mechanism_code,
        phase_code=payload.phase_code,
        type_code=payload.type_code,
        status_code=payload.status_code,
        pop_start=payload.pop_start,
        pop_end=payload.pop_end,
        funded_through=payload.funded_through,
        awarded_cost_cents=payload.awarded_cost_cents,
        funded_amount_cents=payload.funded_amount_cents,
        fee_pot_cents=payload.fee_pot_cents,
        enforce_ceiling=award_type.enforce_ceiling,
        labor_incurred=award_type.labor_incurred,
        fee_engine=award_type.fee_engine,
        ceiling_warn_pct=award_type.ceiling_warn_pct,
        created_by=actor_id,
    )
    session.add(award)
    session.flush()

    label = "proposal" if payload.status_code == "pipeline" else "awarded"
    version = BudgetVersion(
        award_id=award.award_id,
        label=label,
        is_active=1,
        created_by=actor_id,
    )
    session.add(version)
    session.flush()

    line_specs = payload.budget_lines or _default_budget_lines(session, payload.type_code)
    if (
        payload.fee_pot_cents
        and award_type.fee_engine == "fixed_pot"
        and not any(spec.category_code == "fee" for spec in line_specs)
    ):
        line_specs = [
            *line_specs,
            BudgetLineIn(
                category_code="fee",
                label="Fee",
                approved_cents=payload.fee_pot_cents,
                sort_order=90,
            ),
        ]
    created_lines: list[BudgetLine] = []
    for spec in line_specs:
        approved = spec.approved_cents
        if spec.category_code == "fee" and approved == 0 and payload.fee_pot_cents:
            approved = payload.fee_pot_cents
        line = BudgetLine(
            budget_version_id=version.budget_version_id,
            category_code=spec.category_code,
            label=spec.label,
            approved_cents=approved,
            sort_order=spec.sort_order,
        )
        session.add(line)
        created_lines.append(line)
    session.flush()

    fields = _resolve_policy_fields(session, payload.rate_policy)
    effective_from = payload.rate_policy.effective_from or payload.pop_start
    policy = AwardRatePolicy(
        award_id=award.award_id,
        effective_from=effective_from,
        effective_to=None,
        labor_budget_line_id=_personnel_line_id(created_lines),
        created_by=actor_id,
        **fields,  # type: ignore[arg-type]
    )
    session.add(policy)
    session.flush()
    _add_overrides(session, policy, payload.rate_policy)

    for clin in payload.clins:
        _add_clin(session, award.award_id, clin)

    session.flush()
    record_event(
        session,
        action="award_create",
        entity_type="award",
        entity_id=award.award_id,
        actor_user_id=actor_id,
        detail={"short_code": award.short_code, "type_code": award.type_code},
    )
    return award


def _add_clin(session: Session, award_id: int, clin: ClinIn) -> Clin:
    row = Clin(
        award_id=award_id,
        clin_number=clin.clin_number,
        description=clin.description,
        amount_cents=clin.amount_cents,
        is_option=_as_int_flag(clin.is_option),
        exercise_window_start=clin.exercise_window_start,
        exercise_window_end=clin.exercise_window_end,
        exercised_at=clin.exercised_at,
    )
    session.add(row)
    return row


def revise_rate_policy(
    session: Session, award: Award, incoming: RatePolicyIn, *, actor_id: int | None
) -> AwardRatePolicy:
    """Insert a new policy row and close the previous one (D5)."""
    fields = _resolve_policy_fields(session, incoming)
    effective_from = incoming.effective_from or datetime.now(UTC).date().isoformat()
    _close_open_policies(session, award.award_id, effective_from)
    current = current_policy(session, award.award_id)
    labor_line = current.labor_budget_line_id if current else None
    policy = AwardRatePolicy(
        award_id=award.award_id,
        effective_from=effective_from,
        effective_to=None,
        labor_budget_line_id=labor_line,
        created_by=actor_id,
        **fields,  # type: ignore[arg-type]
    )
    session.add(policy)
    session.flush()
    _add_overrides(session, policy, incoming)
    record_event(
        session,
        action="rate_policy_revision",
        entity_type="award_rate_policy",
        entity_id=policy.policy_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id},
    )
    return policy


def apply_mod(
    session: Session, award: Award, payload: AwardModCreate, *, actor_id: int | None
) -> AwardMod:
    """Record a mod, update current award fields, and optionally a new budget version."""
    existing = session.scalar(
        select(AwardMod).where(
            AwardMod.award_id == award.award_id,
            AwardMod.mod_number == payload.mod_number,
        )
    )
    if existing is not None:
        raise AwardError(f"mod {payload.mod_number} already exists on this award")

    mod = AwardMod(
        award_id=award.award_id,
        mod_number=payload.mod_number,
        effective_date=payload.effective_date,
        description=payload.description,
        awarded_cost_cents=payload.awarded_cost_cents,
        funded_amount_cents=payload.funded_amount_cents,
        fee_pot_cents=payload.fee_pot_cents,
        pop_start=payload.pop_start,
        pop_end=payload.pop_end,
        funded_through=payload.funded_through,
        created_by=actor_id,
    )
    session.add(mod)

    if payload.awarded_cost_cents is not None:
        award.awarded_cost_cents = payload.awarded_cost_cents
    if payload.funded_amount_cents is not None:
        award.funded_amount_cents = payload.funded_amount_cents
    if payload.fee_pot_cents is not None:
        award.fee_pot_cents = payload.fee_pot_cents
    if payload.pop_start is not None:
        award.pop_start = payload.pop_start
    if payload.pop_end is not None:
        award.pop_end = payload.pop_end
    if payload.funded_through is not None:
        award.funded_through = payload.funded_through

    if payload.budget_line_changes:
        _apply_budget_changes(
            session, award, payload.budget_line_changes, payload.mod_number, actor_id
        )

    if payload.rate_policy is not None:
        if payload.rate_policy.effective_from is None:
            payload.rate_policy.effective_from = payload.effective_date
        revise_rate_policy(session, award, payload.rate_policy, actor_id=actor_id)

    session.flush()
    return mod


def _apply_budget_changes(
    session: Session,
    award: Award,
    changes: list[BudgetLineChange],
    mod_number: str,
    actor_id: int | None,
) -> None:
    current = active_budget_version(session, award.award_id)
    if current is None:
        raise AwardError("award has no active budget")
    current.is_active = 0
    new_version = BudgetVersion(
        award_id=award.award_id,
        label=f"mod {mod_number}",
        is_active=1,
        created_by=actor_id,
    )
    session.add(new_version)
    session.flush()

    old_lines = session.scalars(
        select(BudgetLine)
        .where(BudgetLine.budget_version_id == current.budget_version_id)
        .order_by(BudgetLine.sort_order)
    ).all()
    by_category = {item.category_code: item for item in changes}
    copied: list[BudgetLine] = []
    for old in old_lines:
        change = by_category.pop(old.category_code, None)
        line = BudgetLine(
            budget_version_id=new_version.budget_version_id,
            category_code=old.category_code,
            label=change.label if change and change.label else old.label,
            approved_cents=change.approved_cents if change else old.approved_cents,
            sort_order=old.sort_order,
        )
        session.add(line)
        copied.append(line)
    next_sort = (copied[-1].sort_order + 10) if copied else 10
    for change in by_category.values():
        session.add(
            BudgetLine(
                budget_version_id=new_version.budget_version_id,
                category_code=change.category_code,
                label=change.label,
                approved_cents=change.approved_cents,
                sort_order=next_sort,
            )
        )
        next_sort += 10
    session.flush()
    policy = current_policy(session, award.award_id)
    if policy is not None:
        personnel = session.scalars(
            select(BudgetLine).where(
                BudgetLine.budget_version_id == new_version.budget_version_id,
                BudgetLine.category_code == "personnel",
            )
        ).first()
        if personnel is not None:
            policy.labor_budget_line_id = personnel.budget_line_id


def update_award(session: Session, award: Award, payload: AwardUpdate) -> Award:
    """Patch header fields that are not a formal modification."""
    if payload.title is not None:
        award.title = payload.title.strip()
    if payload.agency is not None:
        record_agency(session, payload.agency)
        award.agency = payload.agency.strip()
    if payload.status_code is not None:
        award.status_code = payload.status_code
    if payload.funded_through is not None:
        award.funded_through = payload.funded_through
    return award


def current_policy(session: Session, award_id: int) -> AwardRatePolicy | None:
    """Return the open (or latest) policy for an award."""
    open_row = session.scalar(
        select(AwardRatePolicy)
        .where(AwardRatePolicy.award_id == award_id, AwardRatePolicy.effective_to.is_(None))
        .order_by(AwardRatePolicy.effective_from.desc())
    )
    if open_row is not None:
        return open_row
    return session.scalar(
        select(AwardRatePolicy)
        .where(AwardRatePolicy.award_id == award_id)
        .order_by(AwardRatePolicy.effective_from.desc())
    )


def active_budget_version(session: Session, award_id: int) -> BudgetVersion | None:
    """Return the active budget version."""
    return session.scalar(
        select(BudgetVersion).where(
            BudgetVersion.award_id == award_id,
            BudgetVersion.is_active == 1,
        )
    )


def remaining_stmt(award_id: int | None = None) -> Select:
    """Select rows from ``v_budget_remaining``."""
    from sqlalchemy import column, table

    view = table(
        "v_budget_remaining",
        column("award_id"),
        column("short_code"),
        column("status_code"),
        column("type_code"),
        column("enforce_ceiling"),
        column("labor_incurred"),
        column("fee_engine"),
        column("fee_pot_cents"),
        column("awarded_cost_cents"),
        column("funded_amount_cents"),
        column("approved_cents"),
        column("committed_cents"),
        column("actual_cents"),
        column("remaining_approved_cents"),
        column("remaining_funded_cents"),
        column("unexercised_option_cents"),
    )
    stmt = select(view)
    if award_id is not None:
        stmt = stmt.where(column("award_id") == award_id)
    return stmt


def line_remaining_map(session: Session, award_id: int) -> dict[int, tuple[int, int, int]]:
    """Map budget_line_id → (actual_cents, committed_cents, remaining_cents)."""
    from sqlalchemy import column, table

    view = table(
        "v_budget_line_remaining",
        column("budget_line_id"),
        column("award_id"),
        column("actual_cents"),
        column("committed_cents"),
        column("remaining_cents"),
    )
    rows = session.execute(select(view).where(column("award_id") == award_id)).mappings().all()
    return {
        int(row["budget_line_id"]): (
            int(row["actual_cents"]),
            int(row["committed_cents"]),
            int(row["remaining_cents"]),
        )
        for row in rows
    }


def remaining_for(session: Session, award_id: int) -> AwardRemainingOut | None:
    """Load one remaining rollup."""
    row = session.execute(remaining_stmt(award_id)).mappings().first()
    if row is None:
        return None
    return _remaining_out(row)


def _remaining_out(row: object) -> AwardRemainingOut:
    data = dict(row)  # type: ignore[arg-type]
    return AwardRemainingOut(
        award_id=int(data["award_id"]),
        short_code=str(data["short_code"]),
        status_code=str(data["status_code"]),
        type_code=str(data["type_code"]),
        enforce_ceiling=bool(data["enforce_ceiling"]),
        labor_incurred=bool(data["labor_incurred"]),
        fee_engine=str(data["fee_engine"]),
        fee_pot_cents=int(data["fee_pot_cents"]),
        awarded_cost_cents=int(data["awarded_cost_cents"]),
        funded_amount_cents=int(data["funded_amount_cents"]),
        approved_cents=int(data["approved_cents"]),
        committed_cents=int(data["committed_cents"]),
        actual_cents=int(data["actual_cents"]),
        remaining_approved_cents=int(data["remaining_approved_cents"]),
        remaining_funded_cents=int(data["remaining_funded_cents"]),
        unexercised_option_cents=int(data["unexercised_option_cents"]),
    )


def serialize_award_card(award: Award) -> AwardCardOut:
    """Employee charge-code card (D18)."""
    return AwardCardOut(
        award_id=award.award_id,
        short_code=award.short_code,
        title=award.title,
        status_code=award.status_code,
        phase_code=award.phase_code,
        type_code=award.type_code,
    )


def serialize_award(session: Session, award: Award) -> AwardOut:
    """Build the API representation of an award."""
    policy = current_policy(session, award.award_id)
    version = active_budget_version(session, award.award_id)
    lines: list[BudgetLine] = []
    if version is not None:
        lines = list(
            session.scalars(
                select(BudgetLine)
                .where(BudgetLine.budget_version_id == version.budget_version_id)
                .order_by(BudgetLine.sort_order)
            )
        )
    clins = list(
        session.scalars(
            select(Clin).where(Clin.award_id == award.award_id).order_by(Clin.clin_number)
        )
    )
    remaining = remaining_for(session, award.award_id)
    line_money = line_remaining_map(session, award.award_id)
    return AwardOut(
        award_id=award.award_id,
        organization_id=award.organization_id,
        short_code=award.short_code,
        title=award.title,
        agency=award.agency,
        instrument_code=award.instrument_code,
        mechanism_code=award.mechanism_code,
        phase_code=award.phase_code,
        type_code=award.type_code,
        status_code=award.status_code,
        pop_start=award.pop_start,
        pop_end=award.pop_end,
        funded_through=award.funded_through,
        awarded_cost_cents=award.awarded_cost_cents,
        funded_amount_cents=award.funded_amount_cents,
        fee_pot_cents=award.fee_pot_cents,
        enforce_ceiling=bool(award.enforce_ceiling),
        labor_incurred=bool(award.labor_incurred),
        fee_engine=award.fee_engine,
        ceiling_warn_pct=award.ceiling_warn_pct,
        current_policy=serialize_policy(session, policy) if policy else None,
        budget_lines=[
            BudgetLineOut(
                budget_line_id=line.budget_line_id,
                category_code=line.category_code,
                label=line.label,
                approved_cents=line.approved_cents,
                actual_cents=line_money.get(line.budget_line_id, (0, 0, line.approved_cents))[0],
                committed_cents=line_money.get(line.budget_line_id, (0, 0, line.approved_cents))[1],
                remaining_cents=line_money.get(
                    line.budget_line_id,
                    (0, 0, 0 if award.status_code == "pipeline" else line.approved_cents),
                )[2],
                sort_order=line.sort_order,
            )
            for line in lines
        ],
        clins=[
            ClinOut(
                clin_id=row.clin_id,
                clin_number=row.clin_number,
                description=row.description,
                amount_cents=row.amount_cents,
                is_option=bool(row.is_option),
                exercise_window_start=row.exercise_window_start,
                exercise_window_end=row.exercise_window_end,
                exercised_at=row.exercised_at,
            )
            for row in clins
        ],
        remaining=remaining,
    )


def serialize_policy(session: Session, policy: AwardRatePolicy) -> RatePolicyOut:
    overrides = session.scalars(
        select(AwardRateOverride).where(AwardRateOverride.policy_id == policy.policy_id)
    ).all()
    return RatePolicyOut(
        policy_id=policy.policy_id,
        award_id=policy.award_id,
        effective_from=policy.effective_from,
        effective_to=policy.effective_to,
        cost_basis_code=policy.cost_basis_code,
        fringe_pct=policy.fringe_pct,
        oh_pct=policy.oh_pct,
        ga_pct=policy.ga_pct,
        fee_pct=policy.fee_pct,
        fee_in_burden=bool(policy.fee_in_burden),
        labor_budget_line_id=policy.labor_budget_line_id,
        overrides=[
            RateOverrideOut(
                override_id=item.override_id,
                person_id=item.person_id,
                labor_category=item.labor_category,
                loaded_rate_cents=item.loaded_rate_cents,
            )
            for item in overrides
        ],
    )
