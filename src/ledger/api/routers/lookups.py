"""Read-only lookups and the growing agency list."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.api.deps import get_current_user, get_db
from ledger.models import UserAccount
from ledger.models.lookups import (
    Agency,
    AwardInstrument,
    AwardMechanism,
    AwardPhase,
    AwardStatus,
    AwardType,
    BudgetCategory,
    BudgetTemplateLine,
    CostBasis,
    RatePolicyTemplate,
)
from ledger.models.time import TimeCode

router = APIRouter(prefix="/lookups", tags=["lookups"])


def _time_codes(session: Session) -> list[dict[str, object]]:
    return [
        {
            "time_code": row.time_code,
            "description": row.description,
            "consumes_award": bool(row.consumes_award),
        }
        for row in session.scalars(select(TimeCode).order_by(TimeCode.time_code))
    ]


@router.get("")
def all_lookups(
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> dict[str, object]:
    """Admin: award-create vocabularies. Employee: time codes only (D18)."""
    if user.role_code != "admin":
        return {"time_codes": _time_codes(session)}
    types = session.scalars(select(AwardType).order_by(AwardType.type_code)).all()
    templates = session.scalars(
        select(RatePolicyTemplate).order_by(RatePolicyTemplate.template_code)
    ).all()
    categories = session.scalars(select(BudgetCategory).order_by(BudgetCategory.sort_order)).all()
    agencies = session.scalars(select(Agency).order_by(Agency.agency_name)).all()
    budget_templates = session.scalars(
        select(BudgetTemplateLine).order_by(
            BudgetTemplateLine.award_type_code, BudgetTemplateLine.sort_order
        )
    ).all()
    return {
        "instruments": [row.instrument_code for row in session.scalars(select(AwardInstrument))],
        "mechanisms": [row.mechanism_code for row in session.scalars(select(AwardMechanism))],
        "phases": [row.phase_code for row in session.scalars(select(AwardPhase))],
        "statuses": [row.status_code for row in session.scalars(select(AwardStatus))],
        "cost_bases": [row.cost_basis_code for row in session.scalars(select(CostBasis))],
        "award_types": [
            {
                "type_code": row.type_code,
                "description": row.description,
                "enforce_ceiling": bool(row.enforce_ceiling),
                "labor_incurred": bool(row.labor_incurred),
                "fee_engine": row.fee_engine,
                "ceiling_warn_pct": row.ceiling_warn_pct,
            }
            for row in types
        ],
        "rate_policy_templates": [
            {
                "template_code": row.template_code,
                "description": row.description,
                "award_type_code": row.award_type_code,
                "cost_basis_code": row.cost_basis_code,
                "fringe_pct": row.fringe_pct,
                "oh_pct": row.oh_pct,
                "ga_pct": row.ga_pct,
                "fee_pct": row.fee_pct,
                "fee_in_burden": bool(row.fee_in_burden),
                "formula": (
                    "loaded = base × (1+fringe) × (1+oh) × (1+ga)" "; if fee_in_burden: × (1+fee)"
                ),
            }
            for row in templates
        ],
        "budget_categories": [
            {
                "category_code": row.category_code,
                "description": row.description,
                "sort_order": row.sort_order,
            }
            for row in categories
        ],
        "budget_templates": [
            {
                "award_type_code": row.award_type_code,
                "category_code": row.category_code,
                "label": row.label,
                "sort_order": row.sort_order,
            }
            for row in budget_templates
        ],
        "agencies": [row.agency_name for row in agencies],
        "time_codes": _time_codes(session),
    }
