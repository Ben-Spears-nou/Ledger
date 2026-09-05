"""Phase 3 acceptance: tasks, assignments, capacity, My week prefill."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee, _put_week

from ledger.db.engine import get_engine


def _task(client: TestClient, token: str, award_id: int, short_code: str, title: str) -> dict:
    response = client.post(
        f"/awards/{award_id}/tasks",
        json={"short_code": short_code, "title": title},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assign(
    client: TestClient,
    token: str,
    *,
    person_id: int,
    award_id: int,
    hours: float,
    effective_from: str,
    task_id: int | None = None,
    effective_to: str | None = None,
) -> dict:
    body: dict[str, object] = {
        "person_id": person_id,
        "award_id": award_id,
        "hours_per_week": hours,
        "effective_from": effective_from,
    }
    if task_id is not None:
        body["task_id"] = task_id
    if effective_to is not None:
        body["effective_to"] = effective_to
    response = client.post("/assignments", json=body, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def test_employee_task_picker_is_slim_and_awards_card_unchanged(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    first = _task(client, admin, award["award_id"], "T1", "Aim 1")
    second = _task(client, admin, award["award_id"], "T2", "Aim 2")
    alex, _ = _employee(client, admin)
    emp = auth_header(alex)

    assert (
        client.post(
            f"/awards/{award['award_id']}/tasks",
            json={"short_code": "NOPE", "title": "nope"},
            headers=emp,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/assignments",
            json={
                "person_id": 1,
                "award_id": award["award_id"],
                "hours_per_week": 8,
                "effective_from": "2026-03-02",
            },
            headers=emp,
        ).status_code
        == 403
    )

    assert (
        client.post(
            f"/people/{1}/capacity",
            json={"effective_from": "2026-01-01", "hours_per_week": 40},
            headers=emp,
        ).status_code
        == 403
    )

    picker = client.get(f"/awards/{award['award_id']}/tasks", headers=emp)
    assert picker.status_code == 200
    cards = picker.json()
    assert {row["short_code"] for row in cards} == {"T1", "T2"}
    assert {row["task_id"] for row in cards} == {first["task_id"], second["task_id"]}
    for row in cards:
        assert set(row) == {"task_id", "award_id", "short_code", "title", "status_code"}

    all_tasks = client.get("/tasks", headers=emp)
    assert all_tasks.status_code == 200
    assert {row["short_code"] for row in all_tasks.json()} >= {"T1", "T2"}

    listed = client.get("/awards", headers=emp)
    assert listed.status_code == 200
    assert set(listed.json()[0]) == {
        "award_id",
        "short_code",
        "title",
        "status_code",
        "phase_code",
        "type_code",
    }


def test_employee_cannot_see_another_persons_assignments_or_capacity(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3B", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, alex_id = _employee(client, admin, "alex")
    sam, sam_id = _employee(client, admin, "sam")
    _assign(
        client,
        admin,
        person_id=sam_id,
        award_id=award["award_id"],
        hours=8,
        effective_from="2026-03-02",
    )
    cap = client.post(
        f"/people/{sam_id}/capacity",
        json={"effective_from": "2026-01-01", "hours_per_week": 40},
        headers=auth_header(admin),
    )
    assert cap.status_code == 201, cap.text

    assert client.get("/assignments", headers=auth_header(alex)).json() == []
    denied = client.get("/assignments", params={"person_id": sam_id}, headers=auth_header(alex))
    assert denied.status_code == 403
    assert client.get(f"/people/{sam_id}/capacity", headers=auth_header(alex)).status_code == 403
    assert client.get(f"/people/{alex_id}/capacity", headers=auth_header(alex)).status_code == 403
    assert (
        client.get(
            "/capacity", params={"week_start": "2026-03-02"}, headers=auth_header(alex)
        ).status_code
        == 403
    )
    own = client.get("/assignments", headers=auth_header(sam))
    assert own.status_code == 200
    assert len(own.json()) == 1
    assert own.json()[0]["person_id"] == sam_id


def test_first_get_prefills_from_assignments_without_dollars(client: TestClient) -> None:
    admin = login(client)
    award_a = _award(
        client, admin, short_code="T3C", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_b = _award(
        client, admin, short_code="T3D", type_code="FFP", template="FFP_INTERNAL", oh_pct=1000
    )
    task = _task(client, admin, award_a["award_id"], "CORE", "Core")
    alex, alex_id = _employee(client, admin)
    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award_a["award_id"],
        task_id=task["task_id"],
        hours=8,
        effective_from="2026-03-01",
    )
    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award_b["award_id"],
        hours=4,
        effective_from="2026-03-01",
    )

    week = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    assert week.status_code == 200, week.text
    payload = week.json()
    assert "amount_cents" not in payload
    assert "loaded_rate_cents" not in str(payload)
    lines = payload["lines"]
    assert len(lines) == 2
    by_award = {line["award_id"]: line for line in lines}
    assert by_award[award_a["award_id"]]["hours"] == 8
    assert by_award[award_a["award_id"]]["task_id"] == task["task_id"]
    assert by_award[award_a["award_id"]]["work_date"] == "2026-03-02"
    assert by_award[award_b["award_id"]]["hours"] == 4
    assert by_award[award_b["award_id"]]["task_id"] is None


def test_saved_week_is_not_rewritten_when_assignments_change(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3E", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, alex_id = _employee(client, admin)
    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award["award_id"],
        hours=8,
        effective_from="2026-03-01",
    )
    first = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    assert first.status_code == 200
    assert first.json()["lines"][0]["hours"] == 8
    saved = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 3, "award_id": award["award_id"]}],
    )
    assert saved["lines"][0]["hours"] == 3
    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award["award_id"],
        hours=40,
        effective_from="2026-03-02",
    )
    again = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    assert again.json()["lines"][0]["hours"] == 3


def test_submit_need_not_match_plan_and_assignments_do_not_post(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3F", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, alex_id = _employee(client, admin)
    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award["award_id"],
        hours=8,
        effective_from="2026-03-01",
    )
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-04", "hours": 2, "award_id": award["award_id"]}],
    )
    submitted = client.post(
        "/me/week/submit",
        params={"week_start": "2026-03-02"},
        headers=auth_header(alex),
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/approvals/{week['timesheet_period_id']}/approve",
        headers=auth_header(admin),
    )
    assert approved.status_code == 200, approved.text
    remaining = client.get(f"/awards/{award['award_id']}/remaining", headers=auth_header(admin))
    assert remaining.status_code == 200
    # 2 hours × $100 base × 1.25 fringe × 1.30 OH × 1.10 G&A = $357.50
    assert remaining.json()["actual_cents"] == 35_750
    with get_engine().connect() as connection:
        charge_count = connection.execute(text("SELECT COUNT(*) FROM charge")).scalar()
        assignment_count = connection.execute(text("SELECT COUNT(*) FROM assignment")).scalar()
    assert charge_count == 1
    assert assignment_count == 1


def test_closed_award_and_task_reject_new_writes(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3G", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    task = _task(client, admin, award["award_id"], "OLD", "Old")
    closed_task = client.patch(
        f"/awards/{award['award_id']}/tasks/{task['task_id']}",
        json={"status_code": "closed"},
        headers=auth_header(admin),
    )
    assert closed_task.status_code == 200
    alex, alex_id = _employee(client, admin)

    blocked_task = client.post(
        "/assignments",
        json={
            "person_id": alex_id,
            "award_id": award["award_id"],
            "task_id": task["task_id"],
            "hours_per_week": 4,
            "effective_from": "2026-03-02",
        },
        headers=auth_header(admin),
    )
    assert blocked_task.status_code == 400

    time_blocked = client.put(
        "/me/week",
        json={
            "week_start": "2026-03-02",
            "lines": [
                {
                    "work_date": "2026-03-02",
                    "hours": 1,
                    "award_id": award["award_id"],
                    "task_id": task["task_id"],
                }
            ],
        },
        headers=auth_header(alex),
    )
    assert time_blocked.status_code == 400

    client.patch(
        f"/awards/{award['award_id']}",
        json={"status_code": "closed"},
        headers=auth_header(admin),
    )
    blocked_award = client.post(
        "/assignments",
        json={
            "person_id": alex_id,
            "award_id": award["award_id"],
            "hours_per_week": 4,
            "effective_from": "2026-03-02",
        },
        headers=auth_header(admin),
    )
    assert blocked_award.status_code == 400
    new_task = client.post(
        f"/awards/{award['award_id']}/tasks",
        json={"short_code": "NEW", "title": "New"},
        headers=auth_header(admin),
    )
    assert new_task.status_code == 400


def test_pto_cannot_carry_task_id(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3H", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    task = _task(client, admin, award["award_id"], "X", "X")
    alex, _ = _employee(client, admin)
    response = client.put(
        "/me/week",
        json={
            "week_start": "2026-03-02",
            "lines": [
                {
                    "work_date": "2026-03-02",
                    "hours": 8,
                    "time_code": "pto",
                    "task_id": task["task_id"],
                }
            ],
        },
        headers=auth_header(alex),
    )
    assert response.status_code == 400, response.text


def test_capacity_revision_is_a_new_row_and_over_capacity_does_not_block(
    client: TestClient,
) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3I", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, alex_id = _employee(client, admin)
    first = client.post(
        f"/people/{alex_id}/capacity",
        json={"effective_from": "2026-01-01", "hours_per_week": 10},
        headers=auth_header(admin),
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/people/{alex_id}/capacity",
        json={"effective_from": "2026-03-01", "hours_per_week": 10},
        headers=auth_header(admin),
    )
    assert second.status_code == 201, second.text
    rows = client.get(f"/people/{alex_id}/capacity", headers=auth_header(admin)).json()
    assert len(rows) == 2
    assert rows[0]["effective_to"] == "2026-02-28"
    assert rows[1]["effective_to"] is None
    assert rows[0]["person_capacity_id"] != rows[1]["person_capacity_id"]

    _assign(
        client,
        admin,
        person_id=alex_id,
        award_id=award["award_id"],
        hours=40,
        effective_from="2026-03-01",
    )
    week = client.get("/capacity", params={"week_start": "2026-03-02"}, headers=auth_header(admin))
    assert week.status_code == 200
    alex_row = next(row for row in week.json() if row["person_id"] == alex_id)
    assert alex_row["capacity_hours"] == 10
    assert alex_row["planned_hours"] == 40
    assert alex_row["over_capacity"] is True

    saved = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 60, "award_id": award["award_id"]}],
    )
    submitted = client.post(
        "/me/week/submit",
        params={"week_start": "2026-03-02"},
        headers=auth_header(alex),
    )
    assert submitted.status_code == 200, submitted.text
    assert saved["hours_total"] == 60
