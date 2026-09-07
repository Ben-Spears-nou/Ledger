"""Phase 9: admin logins, award header, CLINs, unused delete."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee, _put_week

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def _person_id(client: TestClient, token: str, username: str) -> int:
    people = client.get("/people", headers=auth_header(token))
    assert people.status_code == 200, people.text
    return next(row["person_id"] for row in people.json() if row["username"] == username)


def test_lookups_include_phase9_audit_vocab(client: TestClient) -> None:
    admin = login(client)
    lookups = client.get("/lookups", headers=auth_header(admin))
    assert lookups.status_code == 200, lookups.text
    actions = lookups.json()["audit_actions"]
    assert "person_update" in actions
    assert "password_reset" in actions
    assert "award_delete" in actions
    assert "award_update" in actions
    assert "clin_create" in actions
    assert "clin_exercise" in actions


def test_people_list_includes_is_active(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    created = client.post("/people", json={"display_name": "No Login"}, headers=headers)
    assert created.status_code == 201, created.text
    listed = client.get("/people", headers=headers)
    assert listed.status_code == 200
    by_id = {row["person_id"]: row for row in listed.json()}
    ben = next(row for row in listed.json() if row["username"] == "ben")
    assert ben["is_active"] is True
    assert ben["role_code"] == "admin"
    none = by_id[created.json()["person_id"]]
    assert none["username"] is None
    assert none["is_active"] is None
    assert none["role_code"] is None


def test_last_admin_cannot_be_demoted_or_deactivated(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    ben_id = _person_id(client, admin, "ben")
    demote_last = client.patch(f"/people/{ben_id}", json={"role_code": "employee"}, headers=headers)
    assert demote_last.status_code == 409, demote_last.text
    deactivate_last = client.patch(f"/people/{ben_id}", json={"is_active": False}, headers=headers)
    assert deactivate_last.status_code == 409, deactivate_last.text

    other = client.post(
        "/people",
        json={
            "display_name": "Ada Admin",
            "username": "ada9",
            "password": "admin-pass",
            "role_code": "admin",
        },
        headers=headers,
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["person_id"]
    demote_other = client.patch(
        f"/people/{other_id}", json={"role_code": "employee"}, headers=headers
    )
    assert demote_other.status_code == 200, demote_other.text
    assert demote_other.json()["role_code"] == "employee"
    assert demote_other.json()["is_active"] is True

    still_last = client.patch(f"/people/{ben_id}", json={"role_code": "employee"}, headers=headers)
    assert still_last.status_code == 409, still_last.text


def test_password_reset_invalidates_old_token_employee_forbidden(client: TestClient) -> None:
    admin = login(client)
    alex, person_id = _employee(client, admin, "p9emp")
    stale = auth_header(alex)
    assert client.get("/auth/me", headers=stale).status_code == 200

    reset = client.post(
        f"/people/{person_id}/password",
        json={"new_password": "reset-pass"},
        headers=auth_header(admin),
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["username"] == "p9emp"
    assert client.get("/auth/me", headers=stale).status_code == 401
    fresh = login(client, "p9emp", "reset-pass")
    assert client.get("/auth/me", headers=auth_header(fresh)).status_code == 200

    events = client.get("/admin/audit", headers=auth_header(admin))
    assert events.status_code == 200
    blob = json.dumps(events.json())
    assert "password_reset" in blob
    assert "reset-pass" not in blob

    emp = auth_header(fresh)
    assert (
        client.patch(f"/people/{person_id}", json={"role_code": "admin"}, headers=emp).status_code
        == 403
    )
    assert (
        client.post(
            f"/people/{person_id}/password", json={"new_password": "nope"}, headers=emp
        ).status_code
        == 403
    )


def test_unused_award_delete_and_close_used_award(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    unused = _award(
        client, admin, short_code="P9DEL", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    assert unused["can_delete"] is True
    assert unused["type_locked"] is False
    deleted = client.delete(f"/awards/{unused['award_id']}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/awards/{unused['award_id']}", headers=headers).status_code == 404

    used = _award(
        client, admin, short_code="P9USE", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin, "p9time")
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": used["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    approved = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/awards/{used['award_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["can_delete"] is False
    assert detail.json()["type_locked"] is True
    blocked = client.delete(f"/awards/{used['award_id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    closed = client.patch(
        f"/awards/{used['award_id']}", json={"status_code": "closed"}, headers=headers
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status_code"] == "closed"

    emp = auth_header(alex)
    other = _award(
        client, admin, short_code="P9EMP", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    assert client.delete(f"/awards/{other['award_id']}", headers=emp).status_code == 403
    card = client.get(f"/awards/{other['award_id']}", headers=emp)
    assert card.status_code == 200
    assert set(card.json()) == D18_KEYS


def test_award_header_type_lock_and_clin_exercise(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P9HDR", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_id = award["award_id"]
    patched = client.patch(
        f"/awards/{award_id}",
        json={
            "short_code": "P9NEW",
            "instrument_code": "contract",
            "mechanism_code": "STTR",
            "phase_code": "II",
            "type_code": "FFP",
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["short_code"] == "P9NEW"
    assert body["instrument_code"] == "contract"
    assert body["mechanism_code"] == "STTR"
    assert body["phase_code"] == "II"
    assert body["type_code"] == "FFP"
    assert body["enforce_ceiling"] is False
    assert body["fee_engine"] == "none"
    assert body["type_locked"] is False

    remaining_before = client.get(f"/awards/{award_id}/remaining", headers=headers).json()
    created = client.post(
        f"/awards/{award_id}/clins",
        json={
            "clin_number": "0002",
            "description": "Option",
            "amount_cents": 250_000,
            "is_option": True,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    clin_id = created.json()["clin_id"]
    with_option = client.get(f"/awards/{award_id}/remaining", headers=headers).json()
    assert with_option["unexercised_option_cents"] == 250_000
    assert with_option["remaining_funded_cents"] == remaining_before["remaining_funded_cents"]

    exercised = client.post(
        f"/awards/{award_id}/clins/{clin_id}/exercise", json={}, headers=headers
    )
    assert exercised.status_code == 200, exercised.text
    assert exercised.json()["exercised_at"]
    after = client.get(f"/awards/{award_id}/remaining", headers=headers).json()
    assert after["unexercised_option_cents"] == 0
    assert after["remaining_funded_cents"] == remaining_before["remaining_funded_cents"]
    assert client.delete(f"/awards/{award_id}/clins/{clin_id}", headers=headers).status_code == 400

    purchase = client.post(
        "/purchases",
        json={
            "award_id": award_id,
            "category_code": "equipment",
            "amount_cents": 10_000,
            "description": "lock type",
            "effective_date": "2026-04-01",
        },
        headers=headers,
    )
    assert purchase.status_code == 201, purchase.text
    locked = client.patch(f"/awards/{award_id}", json={"type_code": "CPFF"}, headers=headers)
    assert locked.status_code == 400, locked.text
    detail = client.get(f"/awards/{award_id}", headers=headers)
    assert detail.json()["type_locked"] is True
    assert detail.json()["type_code"] == "FFP"

    alex, _ = _employee(client, admin, "p9clin")
    emp = auth_header(alex)
    assert (
        client.post(
            f"/awards/{award_id}/clins",
            json={"clin_number": "x", "amount_cents": 1},
            headers=emp,
        ).status_code
        == 403
    )
    card = client.get(f"/awards/{award_id}", headers=emp)
    assert card.status_code == 200
    assert set(card.json()) == D18_KEYS
    assert "can_delete" not in card.json()
    assert "clins" not in card.json()
