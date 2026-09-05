"""Phase 4 acceptance: purchases, travel, instruments, remaining."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.conftest import auth_header, login
from tests.test_phase2_time import _award, _employee

from ledger.db.engine import get_engine
from ledger.services.commitments import split_cents

D18_KEYS = {"award_id", "short_code", "title", "status_code", "phase_code", "type_code"}


def _remaining(client: TestClient, token: str, award_id: int) -> dict[str, object]:
    response = client.get(f"/awards/{award_id}/remaining", headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()


def _charge_count() -> int:
    with get_engine().connect() as connection:
        return int(connection.execute(text("SELECT COUNT(*) FROM charge")).scalar_one())


def test_split_cents_puts_remainder_on_last_share() -> None:
    assert split_cents(10_000, [(1, 6000), (2, 4000)]) == [(1, 6000), (2, 4000)]
    assert split_cents(10_001, [(1, 6000), (2, 4000)]) == [(1, 6000), (2, 4001)]


def test_open_purchase_reduces_approved_not_actual_post_swaps_commit(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P4A", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    before = _remaining(client, admin, award["award_id"])
    assert before["committed_cents"] == 0
    assert before["actual_cents"] == 0
    funded = before["remaining_funded_cents"]

    created = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "equipment",
            "amount_cents": 10_000,
            "description": "scope",
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["status_code"] == "open"
    assert created.json()["kind"] == "purchase"

    opened = _remaining(client, admin, award["award_id"])
    assert opened["committed_cents"] == 10_000
    assert opened["actual_cents"] == 0
    assert opened["remaining_approved_cents"] == before["remaining_approved_cents"] - 10_000
    assert opened["remaining_funded_cents"] == funded

    posted = client.post(
        f"/commitments/{created.json()['commitment_id']}/post",
        headers=auth_header(admin),
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["status_code"] == "posted"
    assert posted.json()["charge_id"] is not None

    after = _remaining(client, admin, award["award_id"])
    assert after["committed_cents"] == 0
    assert after["actual_cents"] == 10_000
    assert after["remaining_approved_cents"] == opened["remaining_approved_cents"]
    assert after["remaining_funded_cents"] == funded - 10_000


def test_travel_uses_travel_category(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P4T", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        "/travel",
        json={
            "award_id": award["award_id"],
            "amount_cents": 2_500,
            "description": "site visit",
            "effective_date": "2026-05-04",
            "trip_end": "2026-05-06",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    assert created.json()["kind"] == "travel"
    assert created.json()["category_code"] == "travel"


def test_instrument_sixty_forty_and_bad_share_sum(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    left = _award(
        client, admin, short_code="P4L", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    right = _award(
        client, admin, short_code="P4R", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    bad = client.post(
        "/instruments",
        json={
            "short_code": "BAD-SUM",
            "title": "bad",
            "amount_cents": 10_000,
            "category_code": "equipment",
            "effective_from": "2026-06-01",
            "shares": [
                {"award_id": left["award_id"], "share_pct": 250},
                {"award_id": right["award_id"], "share_pct": 150},
            ],
        },
        headers=headers,
    )
    assert bad.status_code == 400, bad.text

    created = client.post(
        "/instruments",
        json={
            "short_code": "MIC-1",
            "title": "Microscope",
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
    body = created.json()
    by_award = {share["award_id"]: share["amount_cents"] for share in body["shares"]}
    assert by_award[left["award_id"]] == 6_000
    assert by_award[right["award_id"]] == 4_000
    assert {row["amount_cents"] for row in body["commitments"]} == {6_000, 4_000}
    assert all(row["kind"] == "instrument" for row in body["commitments"])

    rounded = client.post(
        "/instruments",
        json={
            "short_code": "MIC-2",
            "title": "Remainder",
            "amount_cents": 10_001,
            "category_code": "equipment",
            "effective_from": "2026-06-02",
            "shares": [
                {"award_id": left["award_id"], "share_pct": 6000},
                {"award_id": right["award_id"], "share_pct": 4000},
            ],
        },
        headers=headers,
    )
    assert rounded.status_code == 201, rounded.text
    cents = {share["award_id"]: share["amount_cents"] for share in rounded.json()["shares"]}
    assert cents[left["award_id"]] == 6_000
    assert cents[right["award_id"]] == 4_001

    posted = client.post(f"/instruments/{body['instrument_id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["status_code"] == "posted"
    left_rem = _remaining(client, admin, left["award_id"])
    right_rem = _remaining(client, admin, right["award_id"])
    assert left_rem["actual_cents"] == 6_000
    assert right_rem["actual_cents"] == 4_000
    assert left_rem["committed_cents"] == 6_000
    assert right_rem["committed_cents"] == 4_001


def test_employee_forbidden_and_d18_card_unchanged(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P4E", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "odc",
            "amount_cents": 1_000,
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    alex, _ = _employee(client, admin)
    emp = auth_header(alex)
    payload = {
        "award_id": award["award_id"],
        "category_code": "odc",
        "amount_cents": 500,
        "effective_date": "2026-04-02",
    }
    assert client.post("/purchases", json=payload, headers=emp).status_code == 403
    assert (
        client.post(
            "/travel",
            json={
                "award_id": award["award_id"],
                "amount_cents": 500,
                "effective_date": "2026-04-02",
            },
            headers=emp,
        ).status_code
        == 403
    )
    assert client.get("/instruments", headers=emp).status_code == 403
    assert (
        client.post(
            f"/commitments/{created.json()['commitment_id']}/post",
            headers=emp,
        ).status_code
        == 403
    )
    listed = client.get("/awards", headers=emp)
    assert listed.status_code == 200
    assert set(listed.json()[0]) == D18_KEYS
    detail = client.get(f"/awards/{award['award_id']}", headers=emp)
    assert detail.status_code == 200
    assert set(detail.json()) == D18_KEYS


def test_ffp_over_approved_ok_cpff_blocked(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    cpff = _award(
        client,
        admin,
        short_code="P4C",
        type_code="CPFF",
        template="CPFF_SBIR",
        oh_pct=3000,
        personnel=10_000,
        funded=50_000,
    )
    over = client.post(
        "/purchases",
        json={
            "award_id": cpff["award_id"],
            "category_code": "equipment",
            "amount_cents": 10_001,
            "effective_date": "2026-04-01",
        },
        headers=headers,
    )
    assert over.status_code == 400, over.text

    ffp = _award(
        client,
        admin,
        short_code="P4F",
        type_code="FFP",
        template="FFP_INTERNAL",
        oh_pct=1500,
        personnel=10_000,
        funded=50_000,
    )
    ok = client.post(
        "/purchases",
        json={
            "award_id": ffp["award_id"],
            "category_code": "equipment",
            "amount_cents": 10_001,
            "effective_date": "2026-04-01",
        },
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    rem = _remaining(client, admin, ffp["award_id"])
    assert rem["remaining_approved_cents"] == 10_000 - 10_001


def test_cancel_restores_remaining_and_skips_charge(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P4X", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    before = _remaining(client, admin, award["award_id"])
    created = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "odc",
            "amount_cents": 8_000,
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    charges_before = _charge_count()
    cancelled = client.post(
        f"/commitments/{created.json()['commitment_id']}/cancel",
        headers=auth_header(admin),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status_code"] == "cancelled"
    after = _remaining(client, admin, award["award_id"])
    assert after["committed_cents"] == 0
    assert after["actual_cents"] == 0
    assert after["remaining_approved_cents"] == before["remaining_approved_cents"]
    assert _charge_count() == charges_before


def test_repost_does_not_duplicate_charges(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client, admin, short_code="P4P", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    created = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "odc",
            "amount_cents": 3_000,
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    commitment_id = created.json()["commitment_id"]
    first = client.post(f"/commitments/{commitment_id}/post", headers=auth_header(admin))
    assert first.status_code == 200, first.text
    charges = _charge_count()
    again = client.post(f"/commitments/{commitment_id}/post", headers=auth_header(admin))
    assert again.status_code in {400, 409}, again.text
    assert _charge_count() == charges
    rem = _remaining(client, admin, award["award_id"])
    assert rem["actual_cents"] == 3_000


def test_closed_and_pipeline_reject_purchases(client: TestClient) -> None:
    admin = login(client)
    headers = auth_header(admin)
    closed = _award(
        client, admin, short_code="P4CL", type_code="CPFF", template="CPFF_SBIR", oh_pct=3000
    )
    patched = client.patch(
        f"/awards/{closed['award_id']}",
        json={"status_code": "closed"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    rejected = client.post(
        "/purchases",
        json={
            "award_id": closed["award_id"],
            "category_code": "odc",
            "amount_cents": 100,
            "effective_date": "2026-04-01",
        },
        headers=headers,
    )
    assert rejected.status_code == 400, rejected.text

    pipeline = _award(
        client,
        admin,
        short_code="P4PL",
        type_code="CPFF",
        template="CPFF_SBIR",
        oh_pct=3000,
        status_code="pipeline",
    )
    piped = client.post(
        "/purchases",
        json={
            "award_id": pipeline["award_id"],
            "category_code": "odc",
            "amount_cents": 100,
            "effective_date": "2026-04-01",
        },
        headers=headers,
    )
    assert piped.status_code == 400, piped.text


def test_cpff_post_blocks_when_funded_remaining_would_go_negative(client: TestClient) -> None:
    admin = login(client)
    award = _award(
        client,
        admin,
        short_code="P4FUN",
        type_code="CPFF",
        template="CPFF_SBIR",
        oh_pct=3000,
        personnel=50_000,
        funded=10_000,
    )
    created = client.post(
        "/purchases",
        json={
            "award_id": award["award_id"],
            "category_code": "equipment",
            "amount_cents": 20_000,
            "effective_date": "2026-04-01",
        },
        headers=auth_header(admin),
    )
    assert created.status_code == 201, created.text
    posted = client.post(
        f"/commitments/{created.json()['commitment_id']}/post",
        headers=auth_header(admin),
    )
    assert posted.status_code == 400, posted.text
    rem = _remaining(client, admin, award["award_id"])
    assert rem["committed_cents"] == 20_000
    assert rem["actual_cents"] == 0
