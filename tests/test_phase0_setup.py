"""Phase 0 acceptance tests: the package imports and configuration resolves."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tasks import TASKS

import ledger
from ledger.api.main import app
from ledger.config import PROJECT_ROOT, Settings, get_settings
from ledger.db.bootstrap import init_database


@pytest.fixture
def without_ledger_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide any ``LEDGER_*`` variables exported in the developer's shell."""
    for name in [key for key in os.environ if key.startswith("LEDGER_")]:
        monkeypatch.delenv(name, raising=False)


def test_package_imports_with_version() -> None:
    assert ledger.__version__ == "0.1.0"


def test_expected_subpackages_are_importable() -> None:
    for name in ("config", "db", "db.bootstrap", "models", "schemas", "api", "api.main"):
        assert importlib.import_module(f"ledger.{name}") is not None


def test_project_root_points_at_the_repository() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "docs" / "BUILD_PLAN.md").is_file()
    assert (PROJECT_ROOT / "docs" / "DECISIONS.md").is_file()


def test_schema_sql_exists() -> None:
    """Phase 1 ships the schema; Phase 0 only required that it not be invented early."""
    assert (PROJECT_ROOT / "db" / "schema.sql").is_file()


def test_settings_defaults(without_ledger_env: None) -> None:
    settings = Settings(_env_file=None)
    assert settings.db_url.endswith("ledger.db")
    path = settings.resolved_db_path()
    assert path is not None
    assert path.is_absolute()
    assert path.name == "ledger.db"
    assert path.parent == settings.runtime_dir()
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.log_level == "INFO"


def test_loopback_and_lan_secret_guard() -> None:
    from ledger.config import (
        DEFAULT_SECRET_KEY,
        is_loopback_host,
        lan_bind_blocked_by_default_secret,
    )

    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert not is_loopback_host("0.0.0.0")
    assert lan_bind_blocked_by_default_secret("0.0.0.0", DEFAULT_SECRET_KEY)
    assert not lan_bind_blocked_by_default_secret("0.0.0.0", "not-the-default")
    assert not lan_bind_blocked_by_default_secret("127.0.0.1", DEFAULT_SECRET_KEY)


def test_settings_read_ledger_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGER_API_PORT", "9001")
    monkeypatch.setenv("LEDGER_LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.api_port == 9001
    assert settings.log_level == "DEBUG"


def test_resolved_db_path_is_none_for_non_sqlite_urls() -> None:
    settings = Settings(_env_file=None, db_url="postgresql+psycopg://user:pass@localhost/ledger")
    assert settings.resolved_db_path() is None


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_task_names_match_the_build_plan() -> None:
    assert set(TASKS) == {
        "install",
        "lint",
        "format",
        "test",
        "build-ui",
        "run",
        "db-init",
        "backup",
    }


def test_bootstrap_applies_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LEDGER_DB_URL", f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    monkeypatch.setenv("LEDGER_SECRET_KEY", "test-secret")
    get_settings.cache_clear()
    from ledger.db.engine import get_engine

    get_engine.cache_clear()
    path = init_database()
    assert path is not None
    assert path.exists()
    assert path.stat().st_size > 0
    get_settings.cache_clear()
    get_engine.cache_clear()
