"""Pydantic payloads for awards, policies, budgets, and mods."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RateOverrideIn(BaseModel):
    """Per-person or per-category loaded rate."""

    person_id: int | None = None
    labor_category: str | None = None
    loaded_rate_cents: int = Field(ge=0)


class RatePolicyIn(BaseModel):
    """Labor recipe on create or revision."""

    template_code: str | None = None
    cost_basis_code: str | None = None
    fringe_pct: int | None = Field(default=None, ge=0)
    oh_pct: int | None = Field(default=None, ge=0)
    ga_pct: int | None = Field(default=None, ge=0)
    fee_pct: int | None = Field(default=None, ge=0)
    fee_in_burden: bool | None = None
    effective_from: str | None = None
    overrides: list[RateOverrideIn] = Field(default_factory=list)


class BudgetLineIn(BaseModel):
    """One approved category amount."""

    category_code: str
    label: str | None = None
    approved_cents: int = Field(default=0, ge=0)
    sort_order: int = 0


class ClinIn(BaseModel):
    """Optional CLIN or option line."""

    clin_number: str
    description: str | None = None
    amount_cents: int = Field(default=0, ge=0)
    is_option: bool = False
    exercise_window_start: str | None = None
    exercise_window_end: str | None = None
    exercised_at: str | None = None


class AwardCreate(BaseModel):
    """New-contract intake."""

    short_code: str
    title: str
    agency: str
    instrument_code: str
    mechanism_code: str
    phase_code: str
    type_code: str
    status_code: str = "active"
    pop_start: str
    pop_end: str
    funded_through: str | None = None
    awarded_cost_cents: int = Field(default=0, ge=0)
    funded_amount_cents: int = Field(default=0, ge=0)
    fee_pot_cents: int = Field(default=0, ge=0)
    rate_policy: RatePolicyIn
    budget_lines: list[BudgetLineIn] | None = None
    clins: list[ClinIn] = Field(default_factory=list)


class AwardUpdate(BaseModel):
    """Partial award header edit (not a formal mod)."""

    short_code: str | None = None
    title: str | None = None
    agency: str | None = None
    instrument_code: str | None = None
    mechanism_code: str | None = None
    phase_code: str | None = None
    type_code: str | None = None
    status_code: str | None = None
    funded_through: str | None = None
    overrun_policy: str | None = None


class ClinUpdate(BaseModel):
    """Patch a CLIN. Exercised_at is set via the exercise route."""

    clin_number: str | None = None
    description: str | None = None
    amount_cents: int | None = Field(default=None, ge=0)
    is_option: bool | None = None
    exercise_window_start: str | None = None
    exercise_window_end: str | None = None


class ClinExerciseIn(BaseModel):
    """Mark an option CLIN exercised (D17, D39)."""

    exercised_at: str | None = None


class BudgetLineChange(BaseModel):
    """Approved-cents change applied when recording a mod."""

    category_code: str
    approved_cents: int = Field(ge=0)
    label: str | None = None


class AwardModCreate(BaseModel):
    """Dated money / PoP change, optionally with budget line updates."""

    mod_number: str
    effective_date: str
    description: str | None = None
    awarded_cost_cents: int | None = Field(default=None, ge=0)
    funded_amount_cents: int | None = Field(default=None, ge=0)
    fee_pot_cents: int | None = Field(default=None, ge=0)
    pop_start: str | None = None
    pop_end: str | None = None
    funded_through: str | None = None
    budget_line_changes: list[BudgetLineChange] = Field(default_factory=list)
    rate_policy: RatePolicyIn | None = None


class RateOverrideOut(BaseModel):
    """Stored override."""

    override_id: int
    person_id: int | None
    labor_category: str | None
    loaded_rate_cents: int


class RatePolicyOut(BaseModel):
    """Stored policy row."""

    policy_id: int
    award_id: int
    effective_from: str
    effective_to: str | None
    cost_basis_code: str
    fringe_pct: int
    oh_pct: int
    ga_pct: int
    fee_pct: int
    fee_in_burden: bool
    labor_budget_line_id: int | None
    overrides: list[RateOverrideOut] = Field(default_factory=list)


class BudgetLineOut(BaseModel):
    """Stored line plus remaining (actuals 0 in Phase 1)."""

    budget_line_id: int
    category_code: str
    label: str | None
    approved_cents: int
    committed_cents: int = 0
    actual_cents: int = 0
    remaining_cents: int
    sort_order: int


class ClinOut(BaseModel):
    """Stored CLIN."""

    clin_id: int
    clin_number: str
    description: str | None
    amount_cents: int
    is_option: bool
    exercise_window_start: str | None
    exercise_window_end: str | None
    exercised_at: str | None


class AwardRemainingOut(BaseModel):
    """``v_budget_remaining`` row."""

    award_id: int
    short_code: str
    status_code: str
    type_code: str
    enforce_ceiling: bool
    labor_incurred: bool
    fee_engine: str
    fee_pot_cents: int
    awarded_cost_cents: int
    funded_amount_cents: int
    approved_cents: int
    committed_cents: int
    actual_cents: int
    remaining_approved_cents: int
    remaining_funded_cents: int
    unexercised_option_cents: int
    pipeline_cents: int = 0


class AwardCardOut(BaseModel):
    """Employee-visible charge-code card (D18). No money or rate policy."""

    award_id: int
    short_code: str
    title: str
    status_code: str
    phase_code: str
    type_code: str


class AwardOut(BaseModel):
    """Award header plus current policy, budget, and remaining."""

    award_id: int
    organization_id: int
    short_code: str
    title: str
    agency: str
    instrument_code: str
    mechanism_code: str
    phase_code: str
    type_code: str
    status_code: str
    pop_start: str
    pop_end: str
    funded_through: str | None
    awarded_cost_cents: int
    funded_amount_cents: int
    fee_pot_cents: int
    enforce_ceiling: bool
    labor_incurred: bool
    fee_engine: str
    ceiling_warn_pct: int
    overrun_policy: str = "warn"
    current_policy: RatePolicyOut | None = None
    budget_lines: list[BudgetLineOut] = Field(default_factory=list)
    clins: list[ClinOut] = Field(default_factory=list)
    remaining: AwardRemainingOut | None = None
    can_delete: bool = False
    type_locked: bool = False
