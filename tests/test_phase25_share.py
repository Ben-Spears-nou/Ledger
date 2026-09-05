"""Phase 2.5 acceptance: visibility, password tokens, audit, backup."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee, _put_week

from ledger.backup import backup_sqlite
from ledger.db.engine import get_engine


def _money_keys(blob: object) -> set[str]:
    found: set[str] = set()
    if isinstance(blob, dict):
        for key, value in blob.items():
            if key in {"fringe_pct", "fee_pot", "fee_pot_cents", "oh_pct", "ga_pct", "fee_pct"}:
                found.add(key)
            found |= _money_keys(value)
    elif isinstance(blob, list):
        for item in blob:
            found |= _money_keys(item)
    return found


def test_employee_cannot_see_rates_or_award_money(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="HIDE", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, alex_id = _employee(client, admin, "alex")
    _sam, sam_id = _employee(client, admin, "sam")
    emp = auth_header(alex)

    listed = client.get("/awards", headers=emp)
    assert listed.status_code == 200
    card = listed.json()[0]
    assert set(card) == {
        "award_id",
        "short_code",
        "title",
        "status_code",
        "phase_code",
        "type_code",
    }
    assert _money_keys(listed.json()) == set()

    detail = client.get(f"/awards/{award['award_id']}", headers=emp)
    assert detail.status_code == 200
    assert _money_keys(detail.json()) == set()
    assert "current_policy" not in detail.json()

    remaining = client.get(f"/awards/{award['award_id']}/remaining", headers=emp)
    assert remaining.status_code == 403

    assert client.get("/people", headers=emp).status_code == 403
    assert client.get(f"/people/{sam_id}/rates", headers=emp).status_code == 403
    assert client.get(f"/people/{alex_id}/rates", headers=emp).status_code == 403

    lookups = client.get("/lookups", headers=emp)
    assert lookups.status_code == 200
    assert "time_codes" in lookups.json()
    assert "rate_policy_templates" not in lookups.json()
    assert _money_keys(lookups.json()) == set()

    admin_award = client.get(f"/awards/{award['award_id']}", headers=auth_header(admin))
    assert admin_award.status_code == 200
    assert admin_award.json()["fee_pot_cents"] == 0
    assert admin_award.json()["current_policy"]["fringe_pct"] == 2500


def test_password_change_invalidates_old_token(client: TestClient) -> None:
    token = login(client)
    headers = auth_header(token)
    changed = client.post(
        "/auth/password",
        json={"current_password": "secret", "new_password": "new-secret"},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    stale = client.get("/auth/me", headers=headers)
    assert stale.status_code == 401
    fresh = login(client, "ben", "new-secret")
    assert client.get("/auth/me", headers=auth_header(fresh)).status_code == 200


def test_approve_writes_audit_event(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="AUD", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
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

    denied = client.get("/admin/audit", headers=auth_header(alex))
    assert denied.status_code == 403
    events = client.get("/admin/audit", headers=auth_header(admin))
    assert events.status_code == 200
    actions = {row["action"] for row in events.json()}
    assert "week_approve" in actions
    assert "week_submit" in actions

    with get_engine().connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM audit_event WHERE action = 'week_approve'")
        ).scalar()
    assert count == 1


def test_backup_creates_timestamped_copy(isolated_db: Path, tmp_path: Path) -> None:
    dest = backup_sqlite(source=isolated_db, dest_dir=tmp_path / "backups")
    assert dest.is_file()
    assert dest.stat().st_size > 0
    assert dest.name.startswith("ledger-")
    assert dest.suffix == ".db"


def test_week_put_rejects_unknown_task_id_and_ignores_extra_fields(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="T3", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    alex, _ = _employee(client, admin)
    rejected = client.put(
        "/me/week",
        json={
            "week_start": "2026-03-02",
            "lines": [
                {
                    "work_date": "2026-03-02",
                    "hours": 2,
                    "award_id": award["award_id"],
                    "task_id": 99,
                }
            ],
        },
        headers=auth_header(alex),
    )
    assert rejected.status_code == 400, rejected.text

    week = _put_week(
        client,
        alex,
        "2026-03-09",
        [
            {
                "work_date": "2026-03-09",
                "hours": 2,
                "award_id": award["award_id"],
                "future_only": "ignored",
            }
        ],
    )
    assert week["lines"][0]["award_id"] == award["award_id"]
    assert week["lines"][0]["hours"] == 2
    assert week["lines"][0]["task_id"] is None
    assert "future_only" not in week["lines"][0]


def test_login_failure_is_audited_without_password(client: TestClient) -> None:
    failed = client.post("/auth/login", json={"username": "ben", "password": "wrong"})
    assert failed.status_code == 401
    admin = login(client)
    events = client.get("/admin/audit", headers=auth_header(admin)).json()
    failures = [row for row in events if row["action"] == "login_failure"]
    assert failures
    blob = json.dumps(failures)
    assert "wrong" not in blob
    assert "secret" not in blob


def test_employee_picker_query_is_slim(client: TestClient) -> None:
    admin = login(client)
    _award(client, admin, short_code="P1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000)
    picker = client.get("/awards", params={"as": "picker"}, headers=auth_header(admin))
    assert picker.status_code == 200
    assert _money_keys(picker.json()) == set()
    assert "short_code" in picker.json()[0]
