"""Phase 1 acceptance: awards, policies, remaining, roles."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login


def _cpff_payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "short_code": "CPFF-1",
        "title": "Phase I CPFF",
        "agency": "NIH",
        "instrument_code": "grant",
        "mechanism_code": "SBIR",
        "phase_code": "I",
        "type_code": "CPFF",
        "status_code": "active",
        "pop_start": "2026-01-01",
        "pop_end": "2026-12-31",
        "awarded_cost_cents": 10_000_000,
        "funded_amount_cents": 8_000_000,
        "fee_pot_cents": 50_000,
        "rate_policy": {
            "template_code": "CPFF_SBIR",
            "fringe_pct": 2500,
            "oh_pct": 3000,
            "ga_pct": 1000,
            "fee_pct": 700,
            "fee_in_burden": False,
        },
        "budget_lines": [
            {
                "category_code": "personnel",
                "label": "Personnel",
                "approved_cents": 5_000_000,
                "sort_order": 10,
            },
            {
                "category_code": "travel",
                "label": "Travel",
                "approved_cents": 100_000,
                "sort_order": 20,
            },
            {"category_code": "fee", "label": "Fee", "approved_cents": 50_000, "sort_order": 90},
        ],
    }
    body.update(overrides)
    return body


def _ffp_payload() -> dict[str, object]:
    return {
        "short_code": "FFP-1",
        "title": "Phase II FFP",
        "agency": "DoD",
        "instrument_code": "contract",
        "mechanism_code": "SBIR",
        "phase_code": "II",
        "type_code": "FFP",
        "status_code": "active",
        "pop_start": "2026-02-01",
        "pop_end": "2027-01-31",
        "awarded_cost_cents": 20_000_000,
        "funded_amount_cents": 20_000_000,
        "fee_pot_cents": 0,
        "rate_policy": {
            "template_code": "FFP_INTERNAL",
            "fringe_pct": 2000,
            "oh_pct": 1500,
            "ga_pct": 800,
            "fee_in_burden": False,
        },
    }


def test_admin_creates_cpff_and_ffp_with_different_policies(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    cpff = client.post("/awards", json=_cpff_payload(), headers=headers)
    assert cpff.status_code == 201, cpff.text
    ffp = client.post("/awards", json=_ffp_payload(), headers=headers)
    assert ffp.status_code == 201, ffp.text

    cpff_body = cpff.json()
    ffp_body = ffp.json()
    assert cpff_body["enforce_ceiling"] is True
    assert cpff_body["fee_engine"] == "fixed_pot"
    assert ffp_body["enforce_ceiling"] is False
    assert ffp_body["fee_engine"] == "none"
    assert cpff_body["current_policy"]["cost_basis_code"] == "fully_burdened"
    assert ffp_body["current_policy"]["cost_basis_code"] == "fully_burdened"
    assert cpff_body["current_policy"]["oh_pct"] == 3000
    assert ffp_body["current_policy"]["oh_pct"] == 1500
    assert {line["category_code"] for line in cpff_body["budget_lines"]} >= {
        "personnel",
        "travel",
        "fee",
    }
    assert {line["category_code"] for line in ffp_body["budget_lines"]} >= {"personnel", "travel"}
    assert "fee" not in {line["category_code"] for line in ffp_body["budget_lines"]}


def test_remaining_zero_actuals_and_travel_mod(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    created = client.post("/awards", json=_cpff_payload(), headers=headers).json()
    remaining = client.get(f"/awards/{created['award_id']}/remaining", headers=headers)
    assert remaining.status_code == 200
    body = remaining.json()
    assert body["actual_cents"] == 0
    assert body["committed_cents"] == 0
    assert body["remaining_approved_cents"] == 5_150_000
    assert body["remaining_funded_cents"] == 8_000_000

    travel_before = next(
        line for line in created["budget_lines"] if line["category_code"] == "travel"
    )
    assert travel_before["remaining_cents"] == 100_000

    modded = client.post(
        f"/awards/{created['award_id']}/mods",
        json={
            "mod_number": "P00001",
            "effective_date": "2026-03-01",
            "description": "Add travel",
            "budget_line_changes": [{"category_code": "travel", "approved_cents": 250_000}],
        },
        headers=headers,
    )
    assert modded.status_code == 201, modded.text
    travel = next(
        line for line in modded.json()["budget_lines"] if line["category_code"] == "travel"
    )
    assert travel["approved_cents"] == 250_000
    assert travel["remaining_cents"] == 250_000
    assert modded.json()["remaining"]["remaining_approved_cents"] == 5_300_000


def test_cpff_fee_is_a_fixed_pot_not_a_percent_of_cost(client: TestClient) -> None:
    token = login(client)
    created = client.post("/awards", json=_cpff_payload(), headers=auth_header(token)).json()
    assert created["fee_pot_cents"] == 50_000
    ten_percent = created["awarded_cost_cents"] * created["current_policy"]["fee_pct"] // 10_000
    assert created["fee_pot_cents"] != ten_percent
    assert created["fee_engine"] == "fixed_pot"


def test_rate_policy_revision_is_a_new_row(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    created = client.post("/awards", json=_cpff_payload(), headers=headers).json()
    old_id = created["current_policy"]["policy_id"]
    old_oh = created["current_policy"]["oh_pct"]
    revised = client.post(
        f"/awards/{created['award_id']}/rate-policies",
        json={"template_code": "CPFF_SBIR", "oh_pct": 4000, "effective_from": "2026-07-01"},
        headers=headers,
    )
    assert revised.status_code == 201, revised.text
    new_policy = revised.json()
    assert new_policy["policy_id"] != old_id
    assert new_policy["oh_pct"] == 4000
    assert new_policy["effective_to"] is None

    detail = client.get(f"/awards/{created['award_id']}", headers=headers).json()
    assert detail["current_policy"]["policy_id"] == new_policy["policy_id"]

    from sqlalchemy import text

    from ledger.db.engine import get_engine

    with get_engine().connect() as connection:
        rows = list(
            connection.execute(
                text(
                    "SELECT policy_id, oh_pct, effective_from, effective_to "
                    "FROM award_rate_policy WHERE award_id = :id ORDER BY policy_id"
                ),
                {"id": created["award_id"]},
            )
        )
    assert len(rows) == 2
    first = next(row for row in rows if row[0] == old_id)
    assert first[1] == old_oh
    assert first[3] is not None


def test_employee_cannot_edit_awards(client: TestClient) -> None:
    admin = login(client)
    created = client.post(
        "/people",
        json={
            "display_name": "Alex",
            "username": "alex",
            "password": "employee-pass",
            "role_code": "employee",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    employee = login(client, "alex", "employee-pass")
    emp_headers = auth_header(employee)
    denied = client.post("/awards", json=_cpff_payload(), headers=emp_headers)
    assert denied.status_code == 403
    award = client.post("/awards", json=_cpff_payload(), headers=auth_header(admin)).json()
    patch = client.patch(
        f"/awards/{award['award_id']}",
        json={"title": "Nope"},
        headers=emp_headers,
    )
    assert patch.status_code == 403
    policy = client.post(
        f"/awards/{award['award_id']}/rate-policies",
        json={"template_code": "CPFF_SBIR", "oh_pct": 1},
        headers=emp_headers,
    )
    assert policy.status_code == 403
    readable = client.get(f"/awards/{award['award_id']}", headers=emp_headers)
    assert readable.status_code == 200


def test_new_agency_does_not_need_a_code_change(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    payload = _cpff_payload(agency="Brand New Office 99", short_code="AG-99")
    created = client.post("/awards", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    lookups = client.get("/lookups", headers=headers).json()
    assert "Brand New Office 99" in lookups["agencies"]


def test_pipeline_and_unexercised_option_are_not_remaining(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    payload = _cpff_payload(
        short_code="PIPE-1",
        status_code="pipeline",
        clins=[
            {
                "clin_number": "0001",
                "description": "Base",
                "amount_cents": 1_000_000,
                "is_option": False,
            },
            {
                "clin_number": "0002",
                "description": "Option",
                "amount_cents": 9_999_999,
                "is_option": True,
            },
        ],
    )
    created = client.post("/awards", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    remaining = created.json()["remaining"]
    assert remaining["remaining_approved_cents"] == 0
    assert remaining["remaining_funded_cents"] == 0
    assert remaining["unexercised_option_cents"] == 9_999_999
    for line in created.json()["budget_lines"]:
        assert line["remaining_cents"] == 0


def test_lookups_expose_rules_profile_difference(client: TestClient) -> None:
    token = login(client)
    lookups = client.get("/lookups", headers=auth_header(token)).json()
    by_code = {row["type_code"]: row for row in lookups["award_types"]}
    assert by_code["CPFF"]["enforce_ceiling"] is True
    assert by_code["grant"]["enforce_ceiling"] is True
    assert by_code["FFP"]["enforce_ceiling"] is False
    assert by_code["internal"]["enforce_ceiling"] is False
    assert by_code["CPFF"]["fee_engine"] == "fixed_pot"
    assert by_code["FFP"]["fee_engine"] == "none"
    assert "formula" in lookups["rate_policy_templates"][0]


def test_employee_can_log_in(client: TestClient) -> None:
    admin = login(client)
    client.post(
        "/people",
        json={
            "display_name": "Sam",
            "username": "sam",
            "password": "sam-pass",
            "role_code": "employee",
        },
        headers=auth_header(admin),
    )
    me = client.get("/auth/me", headers=auth_header(login(client, "sam", "sam-pass")))
    assert me.status_code == 200
    assert me.json()["role_code"] == "employee"
    assert me.json()["username"] == "sam"
