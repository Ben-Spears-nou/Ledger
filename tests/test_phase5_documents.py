"""Phase 5: document register, local files, compliance dates."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee

from ledger.config import PROJECT_ROOT, get_settings
from ledger.db.bootstrap import apply_schema_sql
from ledger.db.engine import get_engine

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def _remaining_approved(client: TestClient, token: str, award_id: int) -> int:
    response = client.get(f"/awards/{award_id}/remaining", headers=auth_header(token))
    assert response.status_code == 200, response.text
    return int(response.json()["remaining_approved_cents"])


def test_document_without_file_then_upload_and_download(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="DOC1", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    before = _remaining_approved(client, admin, award["award_id"])
    created = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "report", "title": "Month 1", "document_date": "2026-04-01"},
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["has_file"] is False
    doc_id = created.json()["document_id"]
    assert _remaining_approved(client, admin, award["award_id"]) == before

    uploaded = client.post(
        f"/documents/{doc_id}/file",
        files={"file": ("month1.txt", b"hello-ledger", "text/plain")},
        headers=auth_header(admin),
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["has_file"] is True
    assert uploaded.json()["original_filename"] == "month1.txt"

    downloaded = client.get(f"/documents/{doc_id}/file", headers=auth_header(admin))
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b"hello-ledger"

    listed = client.get(f"/awards/{award['award_id']}/documents", headers=auth_header(admin))
    assert listed.status_code == 200
    assert listed.json()[0]["document_id"] == doc_id


def test_second_file_conflict_and_bad_suffix(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="DOC2", type_code="FFP", template="FFP_INTERNAL", oh_pct=0
    )
    created = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "other", "title": "bin"},
        headers=auth_header(admin),
    )
    doc_id = created.json()["document_id"]
    bad = client.post(
        f"/documents/{doc_id}/file",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        headers=auth_header(admin),
    )
    assert bad.status_code == 400
    first = client.post(
        f"/documents/{doc_id}/file",
        files={"file": ("ok.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(admin),
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/documents/{doc_id}/file",
        files={"file": ("ok2.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_header(admin),
    )
    assert second.status_code == 409


def test_oversize_file_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ledger.services.documents.MAX_DOCUMENT_BYTES", 8)
    admin = login(client)
    award = _award(
        client, admin, short_code="DOCZ", type_code="FFP", template="FFP_INTERNAL", oh_pct=0
    )
    created = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "other", "title": "big"},
        headers=auth_header(admin),
    )
    doc_id = created.json()["document_id"]
    too_big = client.post(
        f"/documents/{doc_id}/file",
        files={"file": ("notes.txt", b"0123456789", "text/plain")},
        headers=auth_header(admin),
    )
    assert too_big.status_code == 400


def test_employee_forbidden_and_d18_card_unchanged(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="DOC3", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        f"/awards/{award['award_id']}/documents",
        json={"kind_code": "contract", "title": "Prime"},
        headers=auth_header(admin),
    )
    doc_id = created.json()["document_id"]
    client.post(
        f"/awards/{award['award_id']}/compliance",
        json={
            "kind_code": "technical_report",
            "title": "T1",
            "due_date": "2026-06-01",
        },
        headers=auth_header(admin),
    )
    alex, _ = _employee(client, admin, "docemp")
    emp = auth_header(alex)
    assert client.get(f"/awards/{award['award_id']}/documents", headers=emp).status_code == 403
    assert client.get(f"/documents/{doc_id}", headers=emp).status_code == 403
    assert client.get(f"/documents/{doc_id}/file", headers=emp).status_code == 403
    assert (
        client.post(
            f"/documents/{doc_id}/file",
            files={"file": ("x.txt", b"x", "text/plain")},
            headers=emp,
        ).status_code
        == 403
    )
    assert client.get("/compliance", headers=emp).status_code == 403
    lookups = client.get("/lookups", headers=emp)
    assert lookups.status_code == 200
    assert "document_kinds" not in lookups.json()
    card = client.get("/awards", headers=emp)
    assert card.status_code == 200
    assert set(card.json()[0]) == D18_KEYS


def test_compliance_done_and_calendar(client: TestClient) -> None:
    admin = login(client)
    award = _award(client, admin, short_code="CMP1", type_code="grant", template="GRANT", oh_pct=0)
    created = client.post(
        f"/awards/{award['award_id']}/compliance",
        json={
            "kind_code": "pop_end",
            "title": "PoP",
            "due_date": "2026-12-31",
            "notes": "final",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["status_code"] == "open"
    item_id = created.json()["compliance_item_id"]
    calendar = client.get(
        "/compliance",
        params={"due_from": "2026-12-01", "due_to": "2026-12-31"},
        headers=auth_header(admin),
    )
    assert calendar.status_code == 200
    assert any(row["compliance_item_id"] == item_id for row in calendar.json())
    kinds = client.get("/lookups", headers=auth_header(admin)).json()
    assert any(row["kind_code"] == "report" for row in kinds["document_kinds"])
    assert any(row["kind_code"] == "pop_end" for row in kinds["compliance_kinds"])
    patched = client.patch(
        f"/compliance/{item_id}",
        json={"status_code": "done"},
        headers=auth_header(admin),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status_code"] == "done"
    assert patched.json()["completed_at"]


def test_apply_schema_adds_task_id_on_legacy_timesheet_line(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    raw = sqlite3.connect(db_path)
    raw.execute(
        "CREATE TABLE timesheet_line ("
        "timesheet_line_id INTEGER PRIMARY KEY, "
        "timesheet_period_id INTEGER, work_date TEXT, hours_hundredths INTEGER, "
        "time_code TEXT, award_id INTEGER)"
    )
    raw.commit()
    raw.close()
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    script = (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as connection:
        apply_schema_sql(connection, script)
    with engine.connect() as connection:
        cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(timesheet_line)")}
        tables = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert "task_id" in cols
    assert "document" in tables
    assert "compliance_item" in tables
    get_settings.cache_clear()
    get_engine.cache_clear()
