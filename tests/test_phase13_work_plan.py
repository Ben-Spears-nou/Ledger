"""Phase 13: editable schedules and SOW work-progress Gantt."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee

from ledger.config import PROJECT_ROOT

SOW = """\
Section F - Deliveries or Performance
0001 Period of Performance
From
31 Aug 2026
To
30 Aug 2028
4.0 REQUIREMENTS (TASKS):
4.1 Kickoff Meeting
4.1.1 The PI shall coordinate with the technical monitor.
4.2 Procure Materials
4.2.1 The contractor shall procure necessary materials.
4.3 Validate Automation
4.3.1 The contractor shall demonstrate the workflow.
5.0 COORDINATION AND TECHNOLOGY TRANSFER SUPPORT
"""


def test_alembic_head_includes_work_plan() -> None:
    versions = {path.name for path in (PROJECT_ROOT / "alembic" / "versions").glob("*.py")}
    assert "0010_phase13_work_plan.py" in versions


def test_work_plan_propose_confirm_progress_and_gantt(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="P13A",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=0,
    )
    award_id = award["award_id"]

    proposed = client.post(
        f"/awards/{award_id}/work-plan/propose",
        json={"text": SOW},
        headers=auth_header(admin),
    )
    assert proposed.status_code == 200, proposed.text
    draft = proposed.json()["items"]
    assert [row["requirement_code"] for row in draft] == ["4.1", "4.2", "4.3"]
    assert draft[0]["start_date"] == "2026-08-31"
    assert draft[-1]["due_date"] == "2028-08-30"
    assert (
        client.get(
            f"/awards/{award_id}/work-plan",
            headers=auth_header(admin),
        ).json()
        == []
    )

    confirmed = client.post(
        f"/awards/{award_id}/work-plan/confirm",
        json={"items": draft},
        headers=auth_header(admin),
    )
    assert confirmed.status_code == 201, confirmed.text
    rows = confirmed.json()
    assert len(rows) == 3

    item_id = rows[1]["work_plan_item_id"]
    patched = client.patch(
        f"/work-plan/{item_id}",
        json={
            "title": "Procure and inventory materials",
            "percent_complete_bp": 5000,
        },
        headers=auth_header(admin),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["percent_complete_bp"] == 5000

    chart = client.get(
        f"/awards/{award_id}/work-gantt",
        params={"as_of": "2028-09-01"},
        headers=auth_header(admin),
    )
    assert chart.status_code == 200, chart.text
    bar = next(row for row in chart.json()["bars"] if row["work_plan_item_id"] == item_id)
    assert bar["complete_width_pct"] == 50
    assert bar["lane"] == "behind"

    completed = client.patch(
        f"/work-plan/{item_id}",
        json={"percent_complete_bp": 10000},
        headers=auth_header(admin),
    )
    assert completed.status_code == 200
    chart = client.get(
        f"/awards/{award_id}/work-gantt",
        params={"as_of": "2028-09-01"},
        headers=auth_header(admin),
    )
    bar = next(row for row in chart.json()["bars"] if row["work_plan_item_id"] == item_id)
    assert bar["lane"] == "completed"
    assert bar["complete_width_pct"] == 100

    employee, _person_id = _employee(client, admin, username="p13employee")
    assert client.get("/work-gantt", headers=auth_header(employee)).status_code == 403


def test_confirmed_schedule_row_can_be_edited(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="P13EDIT",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=0,
    )
    award_id = award["award_id"]
    created = client.post(
        f"/awards/{award_id}/schedule",
        json={
            "kind_code": "deliverable",
            "title": "Initial title",
            "start_date": "2026-03-01",
            "due_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text

    patched = client.patch(
        f"/schedule/{created.json()['schedule_item_id']}",
        json={
            "title": "Edited title",
            "start_date": "2026-03-15",
            "due_date": "2026-04-15",
        },
        headers=auth_header(admin),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "Edited title"
    assert patched.json()["start_date"] == "2026-03-15"
    assert patched.json()["due_date"] == "2026-04-15"


def test_unused_award_delete_cleans_document_linked_work_plan(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    award = _award(
        client,
        admin,
        short_code="P13DELETE",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=0,
    )
    award_id = award["award_id"]
    created = client.post(
        f"/awards/{award_id}/documents",
        json={"kind_code": "contract", "title": "SOW"},
        headers=headers,
    )
    document_id = created.json()["document_id"]
    uploaded = client.post(
        f"/documents/{document_id}/file",
        files={"file": ("sow.txt", SOW.encode(), "text/plain")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    proposed = client.post(
        f"/awards/{award_id}/work-plan/propose",
        json={"document_id": document_id},
        headers=headers,
    )
    confirmed = client.post(
        f"/awards/{award_id}/work-plan/confirm",
        json={"items": proposed.json()["items"]},
        headers=headers,
    )
    assert confirmed.status_code == 201, confirmed.text

    deleted = client.delete(f"/awards/{award_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/awards/{award_id}", headers=headers).status_code == 404
