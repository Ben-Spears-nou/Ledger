"""Loaded-rate recipe (D11 / D16)."""

from __future__ import annotations

from types import SimpleNamespace

from ledger.rates import fully_burdened_rate_cents, loaded_rate_cents, wrapped_rate_cents


def _recipe(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "cost_basis_code": "fully_burdened",
        "fringe_pct": 2500,
        "oh_pct": 3000,
        "ga_pct": 1000,
        "fee_pct": 700,
        "fee_in_burden": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_wrapped_and_fully_burdened_use_hundredths_of_a_percent() -> None:
    recipe = _recipe()
    base = 10_000
    # 10000 * 1.25 * 1.30 = 16250
    assert wrapped_rate_cents(base, recipe) == 16_250
    # 16250 * 1.10 = 17875; fee not in burden
    assert fully_burdened_rate_cents(base, recipe) == 17_875
    assert loaded_rate_cents(base, recipe) == 17_875


def test_fee_in_burden_multiplies_hourly_rate() -> None:
    recipe = _recipe(fee_in_burden=1)
    # 17875 * 1.07 = 19126.25 -> 19126
    assert loaded_rate_cents(10_000, recipe) == 19_126


def test_override_wins_and_catalog_requires_it() -> None:
    recipe = _recipe(cost_basis_code="catalog")
    assert loaded_rate_cents(10_000, recipe, override_cents=12_345) == 12_345
    try:
        loaded_rate_cents(10_000, recipe)
        raise AssertionError("catalog without override should fail")
    except ValueError:
        pass
