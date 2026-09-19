"""Phase 15: award-type fee rules and FFP monthly billing."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase1_awards import _cpff_payload, _ffp_payload


def _ffp_for_billing(**overrides: object) -> dict[str, object]:
    payload = _ffp_payload()
    payload.update(
        {
            "short_code": "FFP-BILL",
            "pop_start": "2026-01-15",
            "pop_end": "2026-03-14",
            "funded_amount_cents": 120_001,
            "awarded_cost_cents": 120_001,
            "fee_pct": 750,
        }
    )
    payload.update(overrides)
    return payload


def test_ffp_fee_uses_funded_value_and_builds_working_months(client: TestClient) -> None:
    headers = auth_header(login(client))
    response = client.post("/awards", json=_ffp_for_billing(), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["fee_pct"] == 750
    assert body["fee_pot_cents"] == 9_000
    fee = next(line for line in body["budget_lines"] if line["category_code"] == "fee")
    assert fee["approved_cents"] == 9_000
    assert body["current_policy"]["fee_pct"] == 0
    assert body["current_policy"]["fee_in_burden"] is False

    periods = body["billing_periods"]
    assert [(row["period_start"], row["period_end"]) for row in periods] == [
        ("2026-01-15", "2026-02-14"),
        ("2026-02-15", "2026-03-14"),
    ]
    assert [row["scheduled_cents"] for row in periods] == [60_000, 60_001]
    assert sum(row["scheduled_cents"] for row in periods) == body["funded_amount_cents"]


def test_ffp_mod_preserves_submitted_period_and_rebuilds_future(client: TestClient) -> None:
    headers = auth_header(login(client))
    created = client.post(
        "/awards",
        json=_ffp_for_billing(funded_amount_cents=120_000, awarded_cost_cents=240_000),
        headers=headers,
    ).json()
    award_id = created["award_id"]
    first = created["billing_periods"][0]
    submitted = client.post(
        f"/awards/{award_id}/billing-periods/{first['billing_period_id']}/submit",
        json={"submitted_at": "2026-02-15"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["submitted_cents"] == 60_000

    modified = client.post(
        f"/awards/{award_id}/mods",
        json={
            "mod_number": "EXT-1",
            "effective_date": "2026-03-01",
            "funded_amount_cents": 240_000,
            "pop_end": "2026-05-14",
        },
        headers=headers,
    )
    assert modified.status_code == 201, modified.text
    body = modified.json()
    periods = body["billing_periods"]

    assert periods[0]["billing_period_id"] == first["billing_period_id"]
    assert periods[0]["submitted_cents"] == 60_000
    assert [(row["period_start"], row["scheduled_cents"]) for row in periods[1:]] == [
        ("2026-02-15", 60_000),
        ("2026-03-15", 60_000),
        ("2026-04-15", 60_000),
    ]
    assert body["fee_pot_cents"] == 18_000
    fee = next(line for line in body["budget_lines"] if line["category_code"] == "fee")
    assert fee["approved_cents"] == 18_000


def test_create_wizard_payload_creates_ffp_award(client: TestClient) -> None:
    """The New award wizard sends fee_pct plus a prefilled fee line, never a fee pot."""
    headers = auth_header(login(client))
    payload = _ffp_for_billing(
        short_code="FFP-WIZARD",
        funded_amount_cents=45_000_000,
        awarded_cost_cents=45_000_000,
        fee_pct=1000,
        fee_pot_cents=0,
        budget_lines=[
            {
                "category_code": "personnel",
                "label": "Personnel",
                "approved_cents": 35_000_000,
                "sort_order": 10,
            },
            {
                "category_code": "fee",
                "label": "Fee / profit",
                "approved_cents": 4_500_000,
                "sort_order": 60,
            },
        ],
    )
    response = client.post("/awards", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["fee_pot_cents"] == 4_500_000
    fee = next(line for line in body["budget_lines"] if line["category_code"] == "fee")
    assert fee["approved_cents"] == 4_500_000
    assert body["billing_periods"]


def test_fee_inputs_are_enforced_by_award_type(client: TestClient) -> None:
    headers = auth_header(login(client))
    ffp = client.post(
        "/awards",
        json=_ffp_for_billing(short_code="FFP-MANUAL", fee_pot_cents=1),
        headers=headers,
    )
    assert ffp.status_code == 400
    assert "calculated from funded amount" in ffp.text

    cpff_payload = _cpff_payload(short_code="CPFF-PCT")
    cpff_payload["fee_pct"] = 500
    cpff = client.post("/awards", json=cpff_payload, headers=headers)
    assert cpff.status_code == 400
    assert "fixed fee amount" in cpff.text
