"""Phase 8: admin intake UI vocabularies and existing write APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase1_awards import _cpff_payload
from tests.test_phase2_time import _award, _employee

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def test_lookups_expose_audit_vocab_admin_only(client: TestClient) -> None:
    admin = login(client)
    lookups = client.get("/lookups", headers=auth_header(admin))
    assert lookups.status_code == 200, lookups.text
    body = lookups.json()
    assert "week_approve" in body["audit_actions"]
    assert "award_create" in body["audit_actions"]
    assert "person_create" in body["audit_actions"]
    assert "award" in body["audit_entity_types"]
    assert "timesheet_period" in body["audit_entity_types"]

    alex, _ = _employee(client, admin, "p8emp")
    emp = client.get("/lookups", headers=auth_header(alex))
    assert emp.status_code == 200
    assert "audit_actions" not in emp.json()
    assert "audit_entity_types" not in emp.json()
    assert "time_codes" in emp.json()
    card = client.get("/awards", headers=auth_header(alex))
    assert card.status_code == 200
    if card.json():
        assert set(card.json()[0]) == D18_KEYS


def test_admin_person_login_and_rate_then_employee_forbidden(client: TestClient) -> None:
    admin = login(client)
    created = client.post(
        "/people",
        json={
            "display_name": "Pat Intake",
            "username": "pat8",
            "password": "employee-pass",
            "role_code": "employee",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]
    hourly = client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-01-01", "base_rate_cents": 12_500},
        headers=auth_header(admin),
    )
    assert hourly.status_code == 201, hourly.text
    assert hourly.json()["base_rate_cents"] == 12_500
    listed = client.get(f"/people/{person_id}/rates", headers=auth_header(admin))
    assert listed.status_code == 200
    assert listed.json()[-1]["base_rate_cents"] == 12_500

    emp = auth_header(login(client, "pat8", "employee-pass"))
    assert client.post("/people", json={"display_name": "Nope"}, headers=emp).status_code == 403
    assert (
        client.post(
            f"/people/{person_id}/rates",
            json={"effective_from": "2026-06-01", "base_rate_cents": 1},
            headers=emp,
        ).status_code
        == 403
    )


def test_admin_award_header_mod_and_policy_employee_forbidden(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P8W", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_id = award["award_id"]
    patched = client.patch(
        f"/awards/{award_id}",
        json={"title": "Wizard award", "status_code": "active"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "Wizard award"

    modded = client.post(
        f"/awards/{award_id}/mods",
        json={
            "mod_number": "P8M1",
            "effective_date": "2026-06-01",
            "funded_amount_cents": 9_000_000,
            "budget_line_changes": [{"category_code": "travel", "approved_cents": 150_000}],
        },
        headers=headers,
    )
    assert modded.status_code == 201, modded.text
    assert modded.json()["funded_amount_cents"] == 9_000_000

    revised = client.post(
        f"/awards/{award_id}/rate-policies",
        json={"template_code": "CPFF_SBIR", "oh_pct": 3500, "effective_from": "2026-07-01"},
        headers=headers,
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["oh_pct"] == 3500

    alex, _ = _employee(client, admin, "p8deny")
    emp = auth_header(alex)
    assert client.post("/awards", json=_cpff_payload(), headers=emp).status_code == 403
    assert client.patch(f"/awards/{award_id}", json={"title": "no"}, headers=emp).status_code == 403
    assert (
        client.post(
            f"/awards/{award_id}/mods",
            json={"mod_number": "no", "effective_date": "2026-08-01"},
            headers=emp,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/awards/{award_id}/rate-policies",
            json={"oh_pct": 1, "effective_from": "2026-08-01"},
            headers=emp,
        ).status_code
        == 403
    )
    card = client.get(f"/awards/{award_id}", headers=emp)
    assert card.status_code == 200
    assert set(card.json()) == D18_KEYS
