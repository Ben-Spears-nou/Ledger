"""Phase 10: home, staffing, overrun warnings, funding expectations, search."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee, _put_week
from tests.test_phase8_intake import D18_KEYS


def test_home_lists_missing_week_employee_forbidden(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    alex, _ = _employee(client, admin, "p10miss")
    home = client.get("/home", params={"as_of": "2026-03-04"}, headers=headers)
    assert home.status_code == 200, home.text
    names = {row["username"] for row in home.json()["missing_weeks"]}
    assert "ben" in names
    assert "p10miss" in names
    assert home.json()["week_start"] == "2026-03-02"
    assert home.json()["close"]["missing_week_count"] >= 2
    assert client.get("/home", headers=auth_header(alex)).status_code == 403
    assert client.get("/staffing", headers=auth_header(alex)).status_code == 403
    assert client.get("/search", params={"q": "x"}, headers=auth_header(alex)).status_code == 403


def test_staffing_overload_scenario_and_utilization(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    a1 = _award(
        client, admin, short_code="P10A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    a2 = _award(
        client, admin, short_code="P10B", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        "/people",
        json={
            "display_name": "Over Load",
            "username": "overload",
            "password": "employee-pass",
            "role_code": "employee",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]
    client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-01-01", "base_rate_cents": 10_000},
        headers=headers,
    )
    client.post(
        f"/people/{person_id}/capacity",
        json={"effective_from": "2026-01-01", "hours_per_week": 10},
        headers=headers,
    )
    for award in (a1, a2):
        assigned = client.post(
            "/assignments",
            json={
                "person_id": person_id,
                "award_id": award["award_id"],
                "hours_per_week": 8,
                "effective_from": "2026-03-02",
            },
            headers=headers,
        )
        assert assigned.status_code == 201, assigned.text

    board = client.get(
        "/staffing", params={"week_start": "2026-03-02", "weeks": 2}, headers=headers
    )
    assert board.status_code == 200, board.text
    person = next(row for row in board.json()["people"] if row["person_id"] == person_id)
    assert person["overload"] is True
    week = person["weeks"][0]
    assert week["assigned_hours"] == 16
    assert week["capacity_hours"] == 10
    assert any(row["person_id"] == person_id for row in board.json()["utilization"])

    scenario = client.post(
        "/staffing/scenario",
        json={
            "person_id": person_id,
            "award_id": a1["award_id"],
            "hours_per_week": 5,
            "week_start": "2026-03-02",
            "weeks": 2,
        },
        headers=headers,
    )
    assert scenario.status_code == 200, scenario.text
    assert scenario.json()["plan_cents"] is not None
    assert scenario.json()["plan_cents"] == scenario.json()["plan_cents_per_week"] * 2
    listed = client.get("/assignments", params={"person_id": person_id}, headers=headers)
    assert len(listed.json()) == 2


def test_cpff_still_blocks_funded_ffp_warns_assignment_warns(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    tight = _award(
        client,
        admin,
        short_code="P10C",
        type_code="CPFF",
        template="CPFF_SBIR",
        oh_pct=3000,
        funded=1_000,
        personnel=1_000,
    )
    assert tight["overrun_policy"] == "stop"
    alex, person_id = _employee(client, admin, "p10stop")
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 8, "award_id": tight["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    blocked = client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=headers)
    assert blocked.status_code == 409, blocked.text

    ffp = _award(
        client, admin, short_code="P10F", type_code="FFP", template="FFP_INTERNAL", oh_pct=1500
    )
    assert ffp["overrun_policy"] == "warn"
    client.post(
        "/assignments",
        json={
            "person_id": person_id,
            "award_id": ffp["award_id"],
            "hours_per_week": 1,
            "effective_from": "2026-03-09",
        },
        headers=headers,
    )
    week2 = _put_week(
        client,
        alex,
        "2026-03-09",
        [{"work_date": "2026-03-09", "hours": 4, "award_id": ffp["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-09"}, headers=auth_header(alex))
    queued = client.get(f"/approvals/{week2['timesheet_period_id']}", headers=headers)
    assert queued.status_code == 200
    assert any("exceeds assigned" in item for item in queued.json()["warnings"])
    approved = client.post(f"/approvals/{week2['timesheet_period_id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert any("exceeds assigned" in item for item in approved.json()["warnings"])


def test_funding_expectation_not_remaining_and_search(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P10E", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_id = award["award_id"]
    before = client.get(f"/awards/{award_id}/remaining", headers=headers).json()
    created = client.post(
        f"/awards/{award_id}/funding-expectations",
        json={"expected_date": "2026-09-01", "amount_cents": 500_000, "notes": "increment"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    after = client.get(f"/awards/{award_id}/remaining", headers=headers).json()
    assert after["remaining_funded_cents"] == before["remaining_funded_cents"]

    found = client.get("/search", params={"q": "P10E"}, headers=headers)
    assert found.status_code == 200, found.text
    assert any(hit["kind"] == "award" and hit["id"] == award_id for hit in found.json()["hits"])


def test_compliance_document_link_does_not_complete(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P10D", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_id = award["award_id"]
    doc = client.post(
        f"/awards/{award_id}/documents",
        json={"kind_code": "report", "title": "Q1 report"},
        headers=headers,
    )
    assert doc.status_code == 201, doc.text
    item = client.post(
        f"/awards/{award_id}/compliance",
        json={"kind_code": "technical_report", "title": "Q1", "due_date": "2026-04-01"},
        headers=headers,
    )
    assert item.status_code == 201, item.text
    patched = client.patch(
        f"/compliance/{item.json()['compliance_item_id']}",
        json={"document_id": doc.json()["document_id"]},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["document_id"] == doc.json()["document_id"]
    assert patched.json()["status_code"] == "open"


def test_d18_and_my_week_planned_hours_have_no_dollars(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P10P", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, person_id = _employee(client, admin, "p10plan")
    client.post(
        "/assignments",
        json={
            "person_id": person_id,
            "award_id": award["award_id"],
            "hours_per_week": 6,
            "effective_from": "2026-03-02",
        },
        headers=headers,
    )
    week = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    assert week.status_code == 200, week.text
    body = week.json()
    assert "amount_cents" not in body
    assert all("amount_cents" not in line for line in body["lines"])
    assert body["planned"][0]["hours_per_week"] == 6
    assert "plan_cents" not in body["planned"][0]
    card = client.get(f"/awards/{award['award_id']}", headers=auth_header(alex))
    assert card.status_code == 200
    assert set(card.json()) == D18_KEYS
