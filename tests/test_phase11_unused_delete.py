"""Phase 11: unused delete, end dated rows, consumed history stays (D45)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee, _put_week
from tests.test_phase8_intake import D18_KEYS

from ledger.config import PROJECT_ROOT


def _remaining(client: TestClient, token: str, award_id: int) -> dict[str, object]:
    response = client.get(f"/awards/{award_id}/remaining", headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()


def _person_id(client: TestClient, token: str, username: str) -> int:
    people = client.get("/people", headers=auth_header(token))
    assert people.status_code == 200, people.text
    return next(row["person_id"] for row in people.json() if row["username"] == username)


def test_alembic_head_unchanged_and_lookups(client: TestClient) -> None:
    admin = login(client)
    lookups = client.get("/lookups", headers=auth_header(admin))
    assert lookups.status_code == 200, lookups.text
    actions = lookups.json()["audit_actions"]
    assert "assignment_delete" in actions
    assert "person_rate_delete" in actions
    assert "rate_policy_delete" in actions
    assert "instrument_delete" in actions
    versions = [
        path.name
        for path in (PROJECT_ROOT / "alembic" / "versions").glob("*.py")
        if not path.name.startswith("_")
    ]
    assert "0008_phase10_operations.py" in versions
    assert not any(name.startswith("0009") for name in versions)


def test_assignment_delete_reopens_predecessor_and_omits_from_prefill(
    client: TestClient,
) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P11A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, person_id = _employee(client, admin, "p11assign")
    first = client.post(
        "/assignments",
        json={
            "person_id": person_id,
            "award_id": award["award_id"],
            "hours_per_week": 8,
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/assignments",
        json={
            "person_id": person_id,
            "award_id": award["award_id"],
            "hours_per_week": 4,
            "effective_from": "2026-03-02",
        },
        headers=headers,
    )
    assert second.status_code == 201, second.text
    listed = client.get("/assignments", params={"person_id": person_id}, headers=headers)
    by_id = {row["assignment_id"]: row for row in listed.json()}
    assert by_id[first.json()["assignment_id"]]["effective_to"] == "2026-03-01"

    ended = client.patch(
        f"/assignments/{first.json()['assignment_id']}",
        json={"hours_per_week": 6},
        headers=headers,
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["hours_per_week"] == 6

    removed = client.delete(f"/assignments/{second.json()['assignment_id']}", headers=headers)
    assert removed.status_code == 204, removed.text
    reopened = client.get("/assignments", params={"person_id": person_id}, headers=headers)
    assert len(reopened.json()) == 1
    assert reopened.json()[0]["effective_to"] is None
    assert reopened.json()[0]["hours_per_week"] == 6

    capacity = client.get("/capacity", params={"week_start": "2026-03-02"}, headers=headers)
    row = next(item for item in capacity.json() if item["person_id"] == person_id)
    assert row["planned_hours"] == 6

    week = client.get("/me/week", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    assert week.status_code == 200, week.text
    assert week.json()["lines"][0]["hours"] == 6
    assert all(line["hours"] != 4 for line in week.json()["lines"])


def test_unused_rate_delete_reopens_consumed_rate_is_409(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P11R", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, person_id = _employee(client, admin, "p11rate")
    rates = client.get(f"/people/{person_id}/rates", headers=headers).json()
    first_id = rates[0]["person_rate_id"]
    second = client.post(
        f"/people/{person_id}/rates",
        json={"effective_from": "2026-03-09", "base_rate_cents": 20_000},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    after_add = client.get(f"/people/{person_id}/rates", headers=headers).json()
    assert next(row for row in after_add if row["person_rate_id"] == first_id)["effective_to"]

    unused = client.delete(
        f"/people/{person_id}/rates/{second.json()['person_rate_id']}", headers=headers
    )
    assert unused.status_code == 204, unused.text
    reopened = client.get(f"/people/{person_id}/rates", headers=headers).json()
    assert len(reopened) == 1
    assert reopened[0]["person_rate_id"] == first_id
    assert reopened[0]["effective_to"] is None

    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 2, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=headers)
    blocked = client.delete(f"/people/{person_id}/rates/{first_id}", headers=headers)
    assert blocked.status_code == 409, blocked.text


def test_capacity_typo_delete_updates_week(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    _, person_id = _employee(client, admin, "p11cap")
    first = client.post(
        f"/people/{person_id}/capacity",
        json={"effective_from": "2026-01-01", "hours_per_week": 40},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    typo = client.post(
        f"/people/{person_id}/capacity",
        json={"effective_from": "2026-03-02", "hours_per_week": 10},
        headers=headers,
    )
    assert typo.status_code == 201, typo.text
    before = client.get("/capacity", params={"week_start": "2026-03-02"}, headers=headers)
    row = next(item for item in before.json() if item["person_id"] == person_id)
    assert row["capacity_hours"] == 10
    removed = client.delete(
        f"/people/{person_id}/capacity/{typo.json()['person_capacity_id']}",
        headers=headers,
    )
    assert removed.status_code == 204, removed.text
    after = client.get("/capacity", params={"week_start": "2026-03-02"}, headers=headers)
    row = next(item for item in after.json() if item["person_id"] == person_id)
    assert row["capacity_hours"] == 40


def test_person_facts_unused_delete_and_last_admin(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    created = client.post(
        "/people",
        json={"display_name": "Temp Hire", "email": "temp@example.com"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]
    patched = client.patch(
        f"/people/{person_id}",
        json={"display_name": "Renamed Hire", "term_date": "2026-12-31"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["display_name"] == "Renamed Hire"
    assert patched.json()["term_date"] == "2026-12-31"
    assert patched.json()["can_delete"] is True
    removed = client.delete(f"/people/{person_id}", headers=headers)
    assert removed.status_code == 204, removed.text
    listed = client.get("/people", headers=headers).json()
    assert all(row["person_id"] != person_id for row in listed)

    award = _award(
        client, admin, short_code="P11P", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, used_id = _employee(client, admin, "p11used")
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [{"work_date": "2026-03-02", "hours": 1, "award_id": award["award_id"]}],
    )
    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=headers)
    used = client.delete(f"/people/{used_id}", headers=headers)
    assert used.status_code == 409, used.text

    ben_id = _person_id(client, admin, "ben")
    last = client.delete(f"/people/{ben_id}", headers=headers)
    assert last.status_code == 409, last.text


def test_unused_task_and_policy_delete(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P11T", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    unused_task = client.post(
        f"/awards/{award['award_id']}/tasks",
        json={"short_code": "U1", "title": "Unused"},
        headers=headers,
    )
    assert unused_task.status_code == 201, unused_task.text
    used_task = client.post(
        f"/awards/{award['award_id']}/tasks",
        json={"short_code": "U2", "title": "Logged"},
        headers=headers,
    )
    assert used_task.status_code == 201, used_task.text
    gone = client.delete(
        f"/awards/{award['award_id']}/tasks/{unused_task.json()['task_id']}",
        headers=headers,
    )
    assert gone.status_code == 204, gone.text

    alex, _ = _employee(client, admin, "p11task")
    week = _put_week(
        client,
        alex,
        "2026-03-02",
        [
            {
                "work_date": "2026-03-02",
                "hours": 2,
                "award_id": award["award_id"],
                "task_id": used_task.json()["task_id"],
            }
        ],
    )
    blocked_task = client.delete(
        f"/awards/{award['award_id']}/tasks/{used_task.json()['task_id']}",
        headers=headers,
    )
    assert blocked_task.status_code == 409, blocked_task.text

    old_id = award["current_policy"]["policy_id"]
    revised = client.post(
        f"/awards/{award['award_id']}/rate-policies",
        json={"template_code": "CPFF_SBIR", "oh_pct": 4000, "effective_from": "2026-03-09"},
        headers=headers,
    )
    assert revised.status_code == 201, revised.text
    unused_policy = client.delete(
        f"/awards/{award['award_id']}/rate-policies/{revised.json()['policy_id']}",
        headers=headers,
    )
    assert unused_policy.status_code == 204, unused_policy.text
    detail = client.get(f"/awards/{award['award_id']}", headers=headers).json()
    assert detail["current_policy"]["policy_id"] == old_id
    assert detail["current_policy"]["effective_to"] is None

    client.post("/me/week/submit", params={"week_start": "2026-03-02"}, headers=auth_header(alex))
    client.post(f"/approvals/{week['timesheet_period_id']}/approve", headers=headers)
    blocked_policy = client.delete(
        f"/awards/{award['award_id']}/rate-policies/{old_id}", headers=headers
    )
    assert blocked_policy.status_code == 409, blocked_policy.text


def test_document_and_open_compliance_delete(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P11D", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    linked = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "report", "title": "Linked"},
        headers=headers,
    )
    assert linked.status_code == 201, linked.text
    free = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "report", "title": "Free"},
        headers=headers,
    )
    assert free.status_code == 201, free.text
    item = client.post(
        f"/awards/{award['award_id']}/compliance",
        json={"kind_code": "technical_report", "title": "Due", "due_date": "2026-06-01"},
        headers=headers,
    )
    assert item.status_code == 201, item.text
    client.patch(
        f"/compliance/{item.json()['compliance_item_id']}",
        json={"document_id": linked.json()["document_id"]},
        headers=headers,
    )
    blocked = client.delete(f"/documents/{linked.json()['document_id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    gone_doc = client.delete(f"/documents/{free.json()['document_id']}", headers=headers)
    assert gone_doc.status_code == 204, gone_doc.text

    open_item = client.post(
        f"/awards/{award['award_id']}/compliance",
        json={"kind_code": "pop_end", "title": "Typo due", "due_date": "2026-07-01"},
        headers=headers,
    )
    assert open_item.status_code == 201, open_item.text
    gone_item = client.delete(
        f"/compliance/{open_item.json()['compliance_item_id']}", headers=headers
    )
    assert gone_item.status_code == 204, gone_item.text
    calendar = client.get("/compliance", headers=headers).json()
    assert all(
        row["compliance_item_id"] != open_item.json()["compliance_item_id"] for row in calendar
    )


def test_unposted_instrument_delete_clears_remaining(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    left = _award(
        client, admin, short_code="P11L", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    right = _award(
        client, admin, short_code="P11R2", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        "/instruments",
        json={
            "short_code": "P11-MIC",
            "title": "Typo split",
            "amount_cents": 10_000,
            "category_code": "equipment",
            "effective_from": "2026-06-01",
            "shares": [
                {"award_id": left["award_id"], "share_pct": 6000},
                {"award_id": right["award_id"], "share_pct": 4000},
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert _remaining(client, admin, left["award_id"])["committed_cents"] == 6_000
    gone = client.delete(f"/instruments/{created.json()['instrument_id']}", headers=headers)
    assert gone.status_code == 204, gone.text
    assert _remaining(client, admin, left["award_id"])["committed_cents"] == 0
    assert _remaining(client, admin, right["award_id"])["committed_cents"] == 0
    listed = client.get("/instruments", headers=headers).json()
    assert all(row["instrument_id"] != created.json()["instrument_id"] for row in listed)

    posted = client.post(
        "/instruments",
        json={
            "short_code": "P11-POST",
            "title": "Keep",
            "amount_cents": 5_000,
            "category_code": "equipment",
            "effective_from": "2026-06-02",
            "shares": [
                {"award_id": left["award_id"], "share_pct": 5000},
                {"award_id": right["award_id"], "share_pct": 5000},
            ],
        },
        headers=headers,
    )
    assert posted.status_code == 201, posted.text
    client.post(f"/instruments/{posted.json()['instrument_id']}/post", headers=headers)
    blocked = client.delete(f"/instruments/{posted.json()['instrument_id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text


def test_employee_forbidden_and_d18_unchanged(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client, admin, short_code="P11E", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, person_id = _employee(client, admin, "p11emp")
    emp = auth_header(alex)
    assignment = client.post(
        "/assignments",
        json={
            "person_id": person_id,
            "award_id": award["award_id"],
            "hours_per_week": 2,
            "effective_from": "2026-03-02",
        },
        headers=headers,
    ).json()
    rates = client.get(f"/people/{person_id}/rates", headers=headers).json()
    cap = client.post(
        f"/people/{person_id}/capacity",
        json={"effective_from": "2026-01-01", "hours_per_week": 40},
        headers=headers,
    ).json()
    task = client.post(
        f"/awards/{award['award_id']}/tasks",
        json={"short_code": "E1", "title": "Emp"},
        headers=headers,
    ).json()
    doc = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "report", "title": "Emp doc"},
        headers=headers,
    ).json()
    item = client.post(
        f"/awards/{award['award_id']}/compliance",
        json={"kind_code": "pop_end", "title": "Emp due", "due_date": "2026-08-01"},
        headers=headers,
    ).json()
    other = _award(
        client, admin, short_code="P11E2", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    instrument = client.post(
        "/instruments",
        json={
            "short_code": "P11-EMP",
            "title": "Emp split",
            "amount_cents": 2_000,
            "category_code": "equipment",
            "effective_from": "2026-06-01",
            "shares": [
                {"award_id": award["award_id"], "share_pct": 5000},
                {"award_id": other["award_id"], "share_pct": 5000},
            ],
        },
        headers=headers,
    ).json()

    assert (
        client.patch(
            f"/assignments/{assignment['assignment_id']}",
            json={"effective_to": "2026-03-08"},
            headers=emp,
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/assignments/{assignment['assignment_id']}", headers=emp).status_code == 403
    )
    assert client.delete(f"/people/{person_id}", headers=emp).status_code == 403
    assert (
        client.delete(
            f"/people/{person_id}/rates/{rates[0]['person_rate_id']}", headers=emp
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/people/{person_id}/capacity/{cap['person_capacity_id']}", headers=emp
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/awards/{award['award_id']}/tasks/{task['task_id']}", headers=emp
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/awards/{award['award_id']}/rate-policies/{award['current_policy']['policy_id']}",
            headers=emp,
        ).status_code
        == 403
    )
    assert client.delete(f"/documents/{doc['document_id']}", headers=emp).status_code == 403
    assert (
        client.delete(f"/compliance/{item['compliance_item_id']}", headers=emp).status_code == 403
    )
    assert (
        client.delete(f"/instruments/{instrument['instrument_id']}", headers=emp).status_code == 403
    )

    picker = client.get("/awards", params={"as": "picker"}, headers=emp)
    assert picker.status_code == 200
    assert set(picker.json()[0]) == D18_KEYS
