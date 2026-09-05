"""Labor loaded-rate math (D11 / D16). Used by Phase 2 posting and Phase 1 tests."""

from __future__ import annotations

from typing import Protocol


class RateRecipe(Protocol):
    """Minimal policy surface for :func:`loaded_rate_cents`."""

    cost_basis_code: str
    fringe_pct: int
    oh_pct: int
    ga_pct: int
    fee_pct: int
    fee_in_burden: int


def pct_multiplier(pct: int) -> float:
    """Return ``1 + pct/10000`` for a hundredths-of-a-percent integer."""
    return 1.0 + (pct / 10_000.0)


def wrapped_rate_cents(base_cents: int, recipe: RateRecipe) -> int:
    """Base after fringe and overhead, rounded to cents."""
    loaded = base_cents * pct_multiplier(recipe.fringe_pct) * pct_multiplier(recipe.oh_pct)
    return round(loaded)


def fully_burdened_rate_cents(base_cents: int, recipe: RateRecipe) -> int:
    """Wrapped plus G&A, and fee only when ``fee_in_burden`` is set."""
    loaded = wrapped_rate_cents(base_cents, recipe) * pct_multiplier(recipe.ga_pct)
    if recipe.fee_in_burden:
        loaded *= pct_multiplier(recipe.fee_pct)
    return round(loaded)


def loaded_rate_cents(
    base_cents: int, recipe: RateRecipe, override_cents: int | None = None
) -> int:
    """Return the hourly amount that will post for this recipe."""
    if override_cents is not None:
        return override_cents
    if recipe.cost_basis_code == "catalog":
        raise ValueError("catalog cost basis requires an override or rate card")
    if recipe.cost_basis_code == "base":
        return base_cents
    if recipe.cost_basis_code == "wrapped":
        return wrapped_rate_cents(base_cents, recipe)
    if recipe.cost_basis_code == "fully_burdened":
        return fully_burdened_rate_cents(base_cents, recipe)
    raise ValueError(f"unknown cost_basis_code: {recipe.cost_basis_code}")
