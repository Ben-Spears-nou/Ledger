"""Shared fixtures: isolated SQLite database and API client."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ledger.config import get_settings
from ledger.db.bootstrap import init_db
from ledger.db.engine import get_engine, get_sessionmaker


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point settings at a temp SQLite file and initialize the schema."""
    db_path = tmp_path / "ledger.db"
    monkeypatch.setenv("LEDGER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LEDGER_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LEDGER_SECRET_KEY", "test-secret")
    monkeypatch.setenv("LEDGER_BOOTSTRAP_ADMIN_USERNAME", "ben")
    monkeypatch.setenv("LEDGER_BOOTSTRAP_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("LEDGER_BOOTSTRAP_ADMIN_NAME", "Ben")
    get_settings.cache_clear()
    get_engine.cache_clear()
    init_db(force=True)
    return db_path


@pytest.fixture
def db_session(isolated_db: Path) -> Iterator[Session]:
    """Yield a session against the isolated database."""
    session = get_sessionmaker(get_engine())()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(isolated_db: Path) -> Iterator[TestClient]:
    """HTTP client bound to a fresh app and isolated database."""
    from ledger.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def login(client: TestClient, username: str = "ben", password: str = "secret") -> str:
    """Return a bearer token for ``username``."""
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    """Authorization header."""
    return {"Authorization": f"Bearer {token}"}
