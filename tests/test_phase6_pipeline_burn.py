"""Phase 6: pipeline forecast, burn/EAC/runway, 75% and PoP alerts."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def _remaining_approved(client: TestClient, token: str, award_id: int) -> int:
    response = client.get(f"/awards/{award_id}/remaining", headers=auth_header(token))
    assert response.status_code == 200, response.text
    return int(response.json()["remaining_approved_cents"])


def _post_actual(
    client: TestClient,
    token: str,
    award_id: int,
    cents: int,
    work_date: str,
    *,
    category: str = "equipment",
) -> None:
    created = client.post(
        "/purchases",
        json={
            "award_id": award_id,
            "category_code": category,
            "amount_cents": cents,
            "description": "phase6",
            "effective_date": work_date,
        },
        headers=auth_header(token),
    )
    assert created.status_code == 201, created.text
    posted = client.post(
        f"/commitments/{created.json()['commitment_id']}/post",
        headers=auth_header(token),
    )
    assert posted.status_code == 200, posted.text


def test_pipeline_node_is_not_remaining(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P6A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    before = client.get(f"/awards/{award['award_id']}/remaining", headers=auth_header(admin))
    assert before.status_code == 200
    approved = before.json()["remaining_approved_cents"]
    created = client.post(
        f"/awards/{award['award_id']}/pipeline",
        json={
            "kind_code": "next_phase",
            "title": "Phase II",
            "amount_cents": 2_000_000,
            "expected_date": "2027-06-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    after = client.get(f"/awards/{award['award_id']}/remaining", headers=auth_header(admin))
    assert after.json()["remaining_approved_cents"] == approved
    assert after.json()["pipeline_cents"] == 2_000_000
    patched = client.patch(
        f"/pipeline/{created.json()['pipeline_node_id']}",
        json={"amount_cents": 2_500_000},
        headers=auth_header(admin),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["amount_cents"] == 2_500_000
    assert (
        client.get(f"/awards/{award['award_id']}/remaining", headers=auth_header(admin)).json()[
            "remaining_approved_cents"
        ]
        == approved
    )
    listed = client.get(f"/awards/{award['award_id']}/pipeline", headers=auth_header(admin))
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Phase II"


def test_closed_award_rejects_pipeline(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="P6Z",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=0,
        status_code="closed",
    )
    created = client.post(
        f"/awards/{award['award_id']}/pipeline",
        json={"kind_code": "other", "title": "nope", "amount_cents": 1},
        headers=auth_header(admin),
    )
    assert created.status_code == 400


def test_monthly_burn_and_eac(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P6B", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    _post_actual(client, admin, award["award_id"], 6_000, "2026-01-05")
    _post_actual(client, admin, award["award_id"], 4_000, "2026-04-02")
    burn = client.get(
        f"/awards/{award['award_id']}/burn",
        params={"as_of": "2026-01-10"},
        headers=auth_header(admin),
    )
    assert burn.status_code == 200, burn.text
    body = burn.json()
    by_month = {row["year_month"]: row["actual_cents"] for row in body["months"]}
    assert by_month["2026-01"] == 6_000
    assert "2026-04" not in by_month
    assert body["daily_burn_cents"] == 600
    assert body["days_to_pop_end"] == 355
    assert body["eac_cents"] == 6_000 + 600 * 355
    later = client.get(
        f"/awards/{award['award_id']}/burn",
        params={"as_of": "2026-04-30"},
        headers=auth_header(admin),
    )
    months = {row["year_month"]: row["actual_cents"] for row in later.json()["months"]}
    assert months["2026-01"] == 6_000
    assert months["2026-04"] == 4_000


def test_burn_ceiling_and_pop_alerts(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="P6C",
        type_code="CPFF",
        template="CPFF_SBIR",
        oh_pct=3000,
        funded=10_000,
        personnel=10_000,
    )
    _post_actual(client, admin, award["award_id"], 7_500, "2026-03-01")
    early = client.get(
        "/alerts",
        params={"as_of": "2026-06-01", "award_id": award["award_id"]},
        headers=auth_header(admin),
    )
    assert early.status_code == 200, early.text
    codes = {row["alert_code"] for row in early.json()}
    assert "burn_ceiling" in codes
    assert "pop_end" not in codes
    day31 = client.get(
        "/alerts",
        params={"as_of": "2026-11-30", "award_id": award["award_id"]},
        headers=auth_header(admin),
    )
    assert "pop_end" not in {row["alert_code"] for row in day31.json()}
    day30 = client.get(
        "/alerts",
        params={"as_of": "2026-12-01", "award_id": award["award_id"]},
        headers=auth_header(admin),
    )
    assert "pop_end" in {row["alert_code"] for row in day30.json()}


def test_employee_forbidden_and_d18_card_unchanged(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P6E", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    client.post(
        f"/awards/{award['award_id']}/pipeline",
        json={"kind_code": "commercial", "title": "x", "amount_cents": 1},
        headers=auth_header(admin),
    )
    alex, _ = _employee(client, admin, "p6emp")
    emp = auth_header(alex)
    assert client.get(f"/awards/{award['award_id']}/pipeline", headers=emp).status_code == 403
    assert client.get(f"/awards/{award['award_id']}/burn", headers=emp).status_code == 403
    assert client.get("/alerts", headers=emp).status_code == 403
    lookups = client.get("/lookups", headers=emp)
    assert lookups.status_code == 200
    assert "pipeline_kinds" not in lookups.json()
    card = client.get("/awards", headers=emp)
    assert card.status_code == 200
    assert set(card.json()[0]) == D18_KEYS
    kinds = client.get("/lookups", headers=auth_header(admin)).json()
    assert any(row["kind_code"] == "next_phase" for row in kinds["pipeline_kinds"])
    assert _remaining_approved(client, admin, award["award_id"]) >= 0
