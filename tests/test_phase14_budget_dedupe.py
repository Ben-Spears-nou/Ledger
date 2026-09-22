"""Phase 14: one budget line per category, and legacy duplicates collapse."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from tests.conftest import auth_header, login
from tests.test_phase1_awards import _cpff_payload

from ledger.config import PROJECT_ROOT
from ledger.db.bootstrap import apply_schema_sql, dedupe_budget_lines
from ledger.db.engine import get_engine


def _schema_sql() -> str:
    return (PROJECT_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")


def _unique_index_sql(name: str) -> str:
    for statement in _schema_sql().split(";"):
        if name in statement and "CREATE UNIQUE INDEX" in statement.upper():
            return statement.strip()
    raise AssertionError(f"{name} is not declared in db/schema.sql")


def _create_award(client: TestClient, short_code: str) -> tuple[int, int]:
    """Create a CPFF award and return ``(award_id, active budget_version_id)``."""
    headers = auth_header(login(client))
    created = client.post("/awards", json=_cpff_payload(short_code=short_code), headers=headers)
    assert created.status_code == 201, created.text
    award_id = created.json()["award_id"]
    with get_engine().connect() as connection:
        version_id = connection.exec_driver_sql(
            f"SELECT budget_version_id FROM budget_version "
            f"WHERE award_id = {award_id} AND is_active = 1"
        ).scalar()
    return award_id, int(version_id)


def test_template_seeds_do_not_multiply_on_replay(client: TestClient) -> None:
    engine = get_engine()
    with engine.begin() as connection:
        before = connection.exec_driver_sql("SELECT COUNT(*) FROM budget_template_line").scalar()
        apply_schema_sql(connection, _schema_sql())
        after = connection.exec_driver_sql("SELECT COUNT(*) FROM budget_template_line").scalar()
        pairs = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM (SELECT DISTINCT award_type_code, category_code "
            "FROM budget_template_line)"
        ).scalar()
    assert after == before == pairs


def test_duplicate_budget_line_is_rejected(client: TestClient) -> None:
    _, version_id = _create_award(client, "DEDUPE-0")
    engine = get_engine()
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO budget_line (budget_version_id, category_code, label, approved_cents) "
            f"VALUES ({version_id}, 'travel', 'Travel again', 200)"
        )


def test_dedupe_collapses_legacy_duplicates_and_repoints(client: TestClient) -> None:
    _, version_id = _create_award(client, "DEDUPE-1")
    engine = get_engine()
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_budget_line_version_category")
        connection.exec_driver_sql("DROP INDEX uq_budget_template_line_type_category")
        for approved in (25_000, 10_000):
            connection.exec_driver_sql(
                "INSERT INTO budget_line "
                "(budget_version_id, category_code, label, approved_cents) "
                f"VALUES ({version_id}, 'fee', 'Fee', {approved})"
            )
        newest = connection.exec_driver_sql("SELECT last_insert_rowid()").scalar()
        connection.exec_driver_sql(
            "INSERT INTO budget_template_line (award_type_code, category_code, label, sort_order) "
            "VALUES ('CPFF', 'travel', 'Travel', 20)"
        )
        connection.exec_driver_sql(
            "INSERT INTO charge (source, amount_cents, budget_line_id, category_code) "
            f"VALUES ('manual', 500, {newest}, 'fee')"
        )

    with engine.begin() as connection:
        dedupe_budget_lines(connection)
        connection.exec_driver_sql(_unique_index_sql("uq_budget_line_version_category"))
        connection.exec_driver_sql(_unique_index_sql("uq_budget_template_line_type_category"))

    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT budget_line_id, approved_cents FROM budget_line "
            f"WHERE budget_version_id = {version_id} AND category_code = 'fee'"
        ).fetchall()
        assert len(rows) == 1
        keeper, approved = rows[0]
        assert approved == 50_000
        charge_line = connection.exec_driver_sql(
            "SELECT budget_line_id FROM charge WHERE amount_cents = 500"
        ).scalar()
        assert charge_line == keeper
        templates = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM budget_template_line "
            "WHERE award_type_code = 'CPFF' AND category_code = 'travel'"
        ).scalar()
        assert templates == 1


def test_mods_do_not_repeat_budget_lines(client: TestClient) -> None:
    headers = auth_header(login(client))
    award_id, _ = _create_award(client, "DEDUPE-2")

    for index, amount in enumerate((250_000, 300_000), start=1):
        modded = client.post(
            f"/awards/{award_id}/mods",
            json={
                "mod_number": f"P0000{index}",
                "effective_date": "2026-03-01",
                "budget_line_changes": [
                    {"category_code": "travel", "approved_cents": amount},
                ],
            },
            headers=headers,
        )
        assert modded.status_code == 201, modded.text

    body = client.get(f"/awards/{award_id}", headers=headers).json()
    categories = [line["category_code"] for line in body["budget_lines"]]
    assert len(categories) == len(set(categories))
    travel = next(line for line in body["budget_lines"] if line["category_code"] == "travel")
    assert travel["approved_cents"] == 300_000


def test_mod_rejects_same_category_copies(client: TestClient) -> None:
    headers = auth_header(login(client))
    award_id, _ = _create_award(client, "DEDUPE-4")
    modded = client.post(
        f"/awards/{award_id}/mods",
        json={
            "mod_number": "P00010",
            "effective_date": "2026-03-01",
            "budget_line_changes": [
                {"category_code": "travel", "approved_cents": 40_000},
                {"category_code": "travel", "approved_cents": 15_000},
            ],
        },
        headers=headers,
    )
    assert modded.status_code == 400, modded.text
    assert "duplicate budget category" in modded.text


def test_mod_collapses_existing_duplicate_lines(client: TestClient) -> None:
    headers = auth_header(login(client))
    award_id, version_id = _create_award(client, "DEDUPE-5")
    engine = get_engine()
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_budget_line_version_category")
        connection.exec_driver_sql(
            "INSERT INTO budget_line (budget_version_id, category_code, label, approved_cents) "
            f"VALUES ({version_id}, 'travel', 'Travel', 25_000)"
        )
    modded = client.post(
        f"/awards/{award_id}/mods",
        json={
            "mod_number": "P00011",
            "effective_date": "2026-03-01",
            "budget_line_changes": [{"category_code": "odc", "approved_cents": 1}],
        },
        headers=headers,
    )
    assert modded.status_code == 201, modded.text
    body = client.get(f"/awards/{award_id}", headers=headers).json()
    travel = next(line for line in body["budget_lines"] if line["category_code"] == "travel")
    assert travel["approved_cents"] == 100_000


def test_create_award_rejects_duplicate_categories(client: TestClient) -> None:
    headers = auth_header(login(client))
    payload = _cpff_payload(short_code="DEDUPE-3")
    lines = list(payload["budget_lines"])  # type: ignore[arg-type]
    lines.append(
        {"category_code": "travel", "label": "Travel again", "approved_cents": 1, "sort_order": 30}
    )
    payload["budget_lines"] = lines
    response = client.post("/awards", json=payload, headers=headers)
    assert response.status_code == 400, response.text
    assert "duplicate budget categories" in response.text
