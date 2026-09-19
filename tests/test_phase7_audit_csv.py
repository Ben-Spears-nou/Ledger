"""Phase 7: audit filters and charges CSV."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def test_audit_filter_by_action(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P7A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    listed = client.get("/admin/audit", headers=auth_header(admin))
    assert listed.status_code == 200
    created = client.get(
        "/admin/audit",
        params={"action": "award_create"},
        headers=auth_header(admin),
    )
    assert created.status_code == 200, created.text
    actions = {row["action"] for row in created.json()}
    assert actions == {"award_create"}
    assert created.json()[0]["actor_display_name"]
    assert created.json()[0]["entity_id"] == str(award["award_id"])
    bad = client.get("/admin/audit", params={"occurred_from": "nope"}, headers=auth_header(admin))
    assert bad.status_code == 400


def test_charges_csv_and_employee_forbidden(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P7C", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    purchase = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "equipment",
            "amount_cents": 12_345,
            "description": "csv",
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert purchase.status_code == 201, purchase.text
    posted = client.post(
        f"/commitments/{purchase.json()['commitment_id']}/post",
        headers=auth_header(admin),
    )
    assert posted.status_code == 200, posted.text

    csv_resp = client.get("/admin/charges.csv", headers=auth_header(admin))
    assert csv_resp.status_code == 200, csv_resp.text
    assert "text/csv" in csv_resp.headers["content-type"]
    text = csv_resp.text
    assert text.startswith("charge_id,")
    assert "amount_cents" in text.splitlines()[0]
    assert "12345" in text
    assert "P7C" in text
    assert "account_code" not in text.splitlines()[0]
    assert "gl_" not in text.splitlines()[0]

    alex, _ = _employee(client, admin, "p7emp")
    emp = auth_header(alex)
    assert client.get("/admin/audit", headers=emp).status_code == 403
    assert client.get("/admin/charges.csv", headers=emp).status_code == 403
    card = client.get("/awards", headers=emp)
    assert card.status_code == 200
    assert set(card.json()[0]) == D18_KEYS
