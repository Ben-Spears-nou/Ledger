"""Phase 2 acceptance: self-service time, rates, and posted charges."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login


def _award(
    client: TestClient,
    token: str,
    *,
    short_code: str,
    type_code: str,
    template: str,
    oh_pct: int,
    fringe_pct: int = 2500,
    ga_pct: int = 1000,
    funded: int = 8_000_000,
    personnel: int = 5_000_000,
    status_code: str = "active",
) -> dict[str, object]:
    instrument = "grant" if type_code in {"CPFF", "grant"} else "contract"
    if type_code == "internal":
        instrument = "internal"
    body = {
        "short_code": short_code,
        "title": short_code,
        "agency": "NIH",
        "instrument_code": instrument,
        "mechanism_code": "SBIR",
        "phase_code": "I",
        "type_code": type_code,
        "status_code": status_code,
        "pop_start": "2026-01-01",
        "pop_end": "2026-12-31",
        "awarded_cost_cents": funded,
        "funded_amount_cents": funded,
        "fee_pot_cents": 0,
        "rate_policy": {
            "template_code": template,
            "fringe_pct": fringe_pct,
            "oh_pct": oh_pct,
            "ga_pct": ga_pct,
            "fee_in_burden": False,
        },
        "budget_lines": [
            {
                "category_code": "personnel",
                "label": "Personnel",
                "approved_cents": personnel,
                "sort_order": 10,
            }
        ],
    }
    response = client.post("/awards", json=body, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def _employee(client: TestClient, admin: str, username: str = "alex") -> tuple[str, int]:
    created = client.post(
        "/people",
        json={
            "display_name": username.title(),
            "username": username,
            "password": "employee-pass",
            "role_code": "employee",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]
    rate = client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-01-01", "base_rate_cents": 10_000},
        headers=auth_header(admin),
    )
    assert rate.status_code == 201, rate.text
    token = login(client, username, "employee-pass")
    return token, person_id


def _put_week(
    client: TestClient,
    token: str,
    week_start: str,
    lines: list[dict[str, object]],
) -> dict[str, object]:
    response = client.put(
        "/me/week",
        json={"week_start": week_start, "lines": lines},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_employee_cannot_see_another_draft(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin, "alex")
    sam, _ = _employee(client, admin, "sam")
    _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 4, "award_id": award["award_id"]}],
    )
    sam_week = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(sam))
    assert sam_week.status_code == 200
    assert sam_week.json()["lines"] == []
    assert (
        sam_week.json()["person_id"]
        != client.get(
            "/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex)
        ).json()["person_id"]
    )
    assert client.get("/approvals", headers=auth_header(sam)).status_code == 403


def test_approve_moves_actuals_and_remaining(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin)
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": award["award_id"]}],
    )
    assert "amount_cents" not in week
    assert all("amount_cents" not in line for line in week["lines"])
    submitted = client.post(
        "/me/week/submit",
        params={"week_start": "2026-03-02"},
        headers=auth_header(alex),
    )
    assert submitted.status_code == 200
    queue = client.get("/approvals", headers=auth_header(admin))
    assert queue.status_code == 200
    assert queue.json()[0]["amount_cents"] == 35_750
    assert queue.json()[0]["lines"][0]["loaded_rate_cents"] == 17_875
    approved = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve",
        headers=auth_header(admin),
    )
    assert approved.status_code == 200, approved.text
    remaining = client.get(f"/awards/{award['award_id']}/remaining", headers=auth_header(admin))
    assert remaining.json()["actual_cents"] == 35_750
    assert remaining.json()["remaining_approved_cents"] == 5_000_000 - 35_750


def test_same_hours_different_policies_differ_in_dollars(client: TestClient) -> None:
    admin = login(client)
    award_a = _award(
        client, admin, short_code="A-HI", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_b = _award(
        client, admin, short_code="B-LO", type_code="FFP", template="FFP_INTERNAL", oh_pct=1500
    )
    alex, _ = _employee(client, admin)
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [
            {"work_date": "2026-03-02", "hours": 2, "award_id": award_a["award_id"]},
            {"work_date": "2026-03-03", "hours": 2, "award_id": award_b["award_id"]},
        ],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    queue = client.get("/approvals", headers=auth_header(admin)).json()[0]
    amounts = {line["award_id"]: line["amount_cents"] for line in queue["lines"]}
    assert amounts[award_a["award_id"]] != amounts[award_b["award_id"]]
    assert amounts[award_a["award_id"]] == 35_750
    client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=auth_header(admin))


def test_policy_and_person_rate_changes_do_not_rewrite_charges(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, person_id = _employee(client, admin)
    week1 = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    client.post(f"/approvals/{week1['timesheet_period_id']}/approve", headers=auth_header(admin))

    revised = client.post(
        f"/awards/{award['award_id']}/rate-policies",
        json={"template_code": "CPFF_SBIR", "oh_pct": 5000, "effective_from": "2026-03-09"},
        headers=auth_header(admin),
    )
    assert revised.status_code == 201
    client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-03-09", "base_rate_cents": 20_000},
        headers=auth_header(admin),
    )

    week2 = _put_week(
        client,
        alex,
        "2026-03-09",
        [{"work_date": "2026-03-09", "hours": 2, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-09"}, headers=auth_header(alex))
    preview = client.get("/approvals", headers=auth_header(admin)).json()[0]
    assert preview["lines"][0]["amount_cents"] != 35_750

    from sqlalchemy import text

    from ledger.db.engine import get_engine

    with get_engine().connect() as connection:
        old = connection.execute(
            text("SELECT oh_pct, base_rate_cents, amount_cents FROM charge ORDER BY charge_id")
        ).first()
    assert old is not None
    assert old[0] == 3000
    assert old[1] == 10_000
    assert old[2] == 35_750

    client.post(f"/approvals/{week2['timesheet_period_id']}/approve", headers=auth_header(admin))
    with get_engine().connect() as connection:
        rows = list(
            connection.execute(
                text("SELECT oh_pct, base_rate_cents FROM charge ORDER BY charge_id")
            )
        )
    assert rows[0][0] == 3000
    assert rows[1][0] == 5000
    assert rows[0][1] == 10_000
    assert rows[1][1] == 20_000


def test_unconstrained_week_hours(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin)
    short = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 3, "award_id": award["award_id"]}],
    )
    assert short["hours_total"] == 3
    submitted = client.post(
        "/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex)
    )
    assert submitted.status_code == 200
    long = _put_week(
        client,
        alex,
        "2026-03-09",
        [{"work_date": "2026-03-09", "hours": 60, "award_id": award["award_id"]}],
    )
    assert long["hours_total"] == 60
    assert (
        client.post(
            "/me/week/submit", params={"week_start": "2026-03-09"}, headers=auth_header(alex)
        ).status_code
        == 200
    )


def test_ffp_does_not_block_over_ceiling(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="FFP-TINY",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=3000,
        funded=1_000,
        personnel=1_000,
    )
    alex, _ = _employee(client, admin)
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    approved = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve",
        headers=auth_header(admin),
    )
    assert approved.status_code == 200, approved.text
    remaining = client.get(
        f"/awards/{award['award_id']}/remaining", headers=auth_header(admin)
    ).json()
    assert remaining["actual_cents"] > remaining["funded_amount_cents"]
    assert remaining["remaining_funded_cents"] < 0


def test_closed_award_rejects_time(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="OLD", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    client.patch(
        f"/awards/{award['award_id']}",
        json={"status_code": "closed"},
        headers=auth_header(admin),
    )
    alex, _ = _employee(client, admin)
    response = client.put(
        "/me/week",
        json={
            "week_start": "2026-03-02",
            "lines": [{"work_date": "2026-03-02", "hours": 1, "award_id": award["award_id"]}],
        },
        headers=auth_header(alex),
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_reapprove_does_not_duplicate_charges(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin)
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    first = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve", headers=auth_header(admin)
    )
    assert first.status_code == 200
    second = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve", headers=auth_header(admin)
    )
    assert second.status_code == 409
    resubmit = client.post(
        "/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex)
    )
    assert resubmit.status_code == 409
    from sqlalchemy import text

    from ledger.db.engine import get_engine

    with get_engine().connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM charge")).scalar()
    assert count == 1


def test_pto_does_not_consume_award_remaining(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="A1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin)
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 8, "time_code": "pto"}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=auth_header(admin))
    remaining = client.get(
        f"/awards/{award['award_id']}/remaining", headers=auth_header(admin)
    ).json()
    assert remaining["actual_cents"] == 0


def test_salary_derives_hourly_base(client: TestClient) -> None:
    admin = login(client)
    created = client.post(
        "/people",
        json={"display_name": "Salaried"},
        headers=auth_header(admin),
    )
    person_id = created.json()["person_id"]
    rate = client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-01-01", "salary_cents": 20_800_000, "hours_per_year": 2080},
        headers=auth_header(admin),
    )
    assert rate.status_code == 201
    assert rate.json()["base_rate_cents"] == 10_000
