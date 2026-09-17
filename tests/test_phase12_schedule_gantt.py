"""Phase 12: glossary, contract schedule propose/confirm, Gantt (D46–D48)."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from docx import Document as WordDocument
from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee
from tests.test_phase5_documents import D18_KEYS, _remaining_approved

from ledger.config import PROJECT_ROOT
from ledger.services import contract_schedule


def test_alembic_head_is_phase12() -> None:
    versions = {path.name for path in (PROJECT_ROOT / "alembic" / "versions").glob("*.py")}
    assert "0009_phase12_schedule_gantt.py" in versions


def test_glossary_and_search_common_language(client: TestClient) -> None:
    admin = login(client)
    employee, _pid = _employee(client, admin, username="pat")
    terms = client.get("/glossary", headers=auth_header(employee))
    assert terms.status_code == 200, terms.text
    codes = {row["term_code"] for row in terms.json()}
    assert {"remaining", "schedule", "gantt", "award"} <= codes

    found = client.get("/search", params={"q": "whats left"}, headers=auth_header(admin))
    assert found.status_code == 200, found.text
    kinds = {hit["kind"] for hit in found.json()["hits"]}
    assert "glossary" in kinds
    remaining = [hit for hit in found.json()["hits"] if hit["kind"] == "glossary"]
    assert any("Remaining" in hit["label"] for hit in remaining)
    assert remaining[0]["href"].startswith("/help")

    denied = client.get("/search", params={"q": "remaining"}, headers=auth_header(employee))
    assert denied.status_code == 403


def test_propose_does_not_write_confirm_does_not_move_remaining(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P12A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    award_id = award["award_id"]
    before = _remaining_approved(client, admin, award_id)
    listed = client.get(f"/awards/{award_id}/schedule", headers=auth_header(admin))
    assert listed.status_code == 200
    assert listed.json() == []

    proposed = client.post(
        f"/awards/{award_id}/schedule/propose",
        json={},
        headers=auth_header(admin),
    )
    assert proposed.status_code == 200, proposed.text
    items = proposed.json()["items"]
    assert items
    assert all(row["origin_code"] == "template" for row in items)
    still = client.get(f"/awards/{award_id}/schedule", headers=auth_header(admin))
    assert still.json() == []

    confirmed = client.post(
        f"/awards/{award_id}/schedule/confirm",
        json={"items": [{**row, "keep": True} for row in items]},
        headers=auth_header(admin),
    )
    assert confirmed.status_code == 201, confirmed.text
    assert len(confirmed.json()) == len(items)
    assert _remaining_approved(client, admin, award_id) == before

    employee, _pid = _employee(client, admin, username="kim")
    slim = client.get("/awards", headers=auth_header(employee))
    assert slim.status_code == 200
    slim_card = next(row for row in slim.json() if row["award_id"] == award_id)
    assert set(slim_card) == D18_KEYS


def test_extract_from_txt_contract_and_gantt_lanes(client: TestClient) -> None:
    admin = login(client)
    employee, _pid = _employee(client, admin, username="lee")
    award = _award(
        client, admin, short_code="P12B", type_code="FFP", template="FFP_INTERNAL", oh_pct=0
    )
    award_id = award["award_id"]
    created = client.post(
        f"/awards/{award_id}/documents",
        json={"kind_code": "contract", "title": "SOW"},
        headers=auth_header(admin),
    )
    doc_id = created.json()["document_id"]
    upload = client.post(
        f"/documents/{doc_id}/file",
        files={
            "file": (
                "sow.txt",
                b"Deliverable 1: Prototype due 2026-03-15\nIgnore this line\n",
                "text/plain",
            )
        },
        headers=auth_header(admin),
    )
    assert upload.status_code == 200, upload.text

    proposed = client.post(
        f"/awards/{award_id}/schedule/propose",
        json={"document_id": doc_id},
        headers=auth_header(admin),
    )
    assert proposed.status_code == 200, proposed.text
    extracted = [row for row in proposed.json()["items"] if row["origin_code"] == "extract"]
    assert extracted
    assert any("2026-03-15" == row["due_date"] for row in extracted)

    kept = [row for row in extracted if row["due_date"] == "2026-03-15"][:1]
    kept[0]["keep"] = True
    saved = client.post(
        f"/awards/{award_id}/schedule/confirm",
        json={"items": kept},
        headers=auth_header(admin),
    )
    assert saved.status_code == 201, saved.text
    item_id = saved.json()[0]["schedule_item_id"]

    behind = client.get(
        f"/awards/{award_id}/gantt",
        params={"as_of": "2026-03-16"},
        headers=auth_header(admin),
    )
    assert behind.status_code == 200, behind.text
    assert behind.json()["bars"][0]["lane"] == "behind"

    done = client.patch(
        f"/schedule/{item_id}",
        json={"status_code": "done"},
        headers=auth_header(admin),
    )
    assert done.status_code == 200
    completed = client.get(
        "/gantt",
        params={"as_of": "2026-03-16"},
        headers=auth_header(admin),
    )
    assert completed.status_code == 200
    bar = next(row for row in completed.json()["bars"] if row["schedule_item_id"] == item_id)
    assert bar["lane"] == "completed"

    assert client.get("/gantt", headers=auth_header(employee)).status_code == 403
    assert (
        client.post(
            f"/awards/{award_id}/schedule/propose",
            json={},
            headers=auth_header(employee),
        ).status_code
        == 403
    )


def test_extract_common_contract_dates_and_wrapped_lines() -> None:
    award = SimpleNamespace(award_id=7, pop_start="2026-01-01")
    text = """\
Deliverable A due 6/15/2026
Milestone B due 15 July 2026
Progress report due August 2026
CDRL A004 due Month 6 after award
Deliverable E
September 15, 2026
"""
    rows = contract_schedule.extract_dated_lines(text, award, source_document_id=12)

    assert [row.due_date for row in rows] == [
        "2026-06-15",
        "2026-07-15",
        "2026-08-31",
        "2026-07-01",
        "2026-09-15",
    ]
    assert all(row.origin_code == "extract" for row in rows)
    assert all(row.source_document_id == 12 for row in rows)


def test_extract_from_docx_table(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P12DOCX", type_code="FFP", template="FFP_INTERNAL", oh_pct=0
    )
    award_id = award["award_id"]
    created = client.post(
        f"/awards/{award_id}/documents",
        json={"kind_code": "contract", "title": "Word SOW"},
        headers=auth_header(admin),
    )
    doc_id = created.json()["document_id"]

    document = WordDocument()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Deliverable: Prototype review"
    table.cell(0, 1).text = "Due 10/15/2026"
    content = BytesIO()
    document.save(content)
    upload = client.post(
        f"/documents/{doc_id}/file",
        files={
            "file": (
                "sow.docx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_header(admin),
    )
    assert upload.status_code == 200, upload.text

    proposed = client.post(
        f"/awards/{award_id}/schedule/propose",
        json={"document_id": doc_id},
        headers=auth_header(admin),
    )
    assert proposed.status_code == 200, proposed.text
    extracted = [row for row in proposed.json()["items"] if row["origin_code"] == "extract"]
    assert [row["due_date"] for row in extracted] == ["2026-10-15"]


def test_pdf_text_and_scanned_pdf_feedback(tmp_path, monkeypatch) -> None:
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF fake test input")
    row = SimpleNamespace(stored_ext=".pdf")
    monkeypatch.setattr(contract_schedule, "stored_path", lambda _row: path)

    class TextPage:
        def extract_text(self) -> str:
            return "Deliverable A due 2026-05-01"

    monkeypatch.setattr(
        contract_schedule,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[TextPage()]),
    )
    text, note = contract_schedule._read_document_text(row)
    assert text == "Deliverable A due 2026-05-01"
    assert note is None

    class ScannedPage:
        def extract_text(self) -> None:
            return None

    monkeypatch.setattr(
        contract_schedule,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[ScannedPage()]),
    )
    text, note = contract_schedule._read_document_text(row)
    assert text is None
    assert "scanned" in note


def test_pasted_text_without_schedule_rows_returns_note(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P12NOTE", type_code="FFP", template="FFP_INTERNAL", oh_pct=0
    )
    proposed = client.post(
        f"/awards/{award['award_id']}/schedule/propose",
        json={"text": "General contract narrative without a schedule date."},
        headers=auth_header(admin),
    )
    assert proposed.status_code == 200, proposed.text
    assert "no dated deliverable lines found in the pasted text" in proposed.json()["notes"]
