"""Application configuration, loaded from the environment and ``.env``.

Every setting is prefixed ``LEDGER_`` in the environment; see ``.env.example``
for the documented template.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
"""Repository root — the directory containing ``pyproject.toml``."""

DEFAULT_SECRET_KEY = "dev-only-change-me"
"""Shipped HMAC secret. Warn (do not crash) when this is still in use."""


def platform_data_dir() -> Path:
    """Local disk directory for SQLite and other runtime files.

    The repo may live on a UNC share; this path must not. ``LEDGER_DATA_DIR``
    overrides the platform default (``%LOCALAPPDATA%\\ledger`` on Windows).
    """
    configured = os.environ.get("LEDGER_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "ledger"
        return Path.home() / "AppData" / "Local" / "ledger"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "ledger"
    return Path.home() / ".local" / "share" / "ledger"


class Settings(BaseSettings):
    """Runtime configuration for Ledger."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGER_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: str | None = Field(
        default=None,
        description="Local directory for SQLite (if db_url is unset) and runtime files.",
    )
    db_url: str = Field(
        default="",
        description="SQLAlchemy database URL. Empty = sqlite file under the local data dir.",
    )
    api_host: str = Field(
        default="127.0.0.1",
        description="Host uvicorn binds when serving the API.",
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port uvicorn binds when serving the API.",
    )
    log_level: str = Field(
        default="INFO",
        description="Python logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    secret_key: str = Field(
        default=DEFAULT_SECRET_KEY,
        description="HMAC secret for login tokens. Set LEDGER_SECRET_KEY in production.",
    )
    bootstrap_admin_username: str = Field(
        default="ben",
        description="Created on first db-init if the user table is empty.",
    )
    bootstrap_admin_password: str = Field(
        default="changeme",
        description="Initial admin password. Change after first login.",
    )
    bootstrap_admin_name: str = Field(
        default="Ben",
        description="Display name for the bootstrap admin person.",
    )

    @model_validator(mode="after")
    def _default_sqlite_under_data_dir(self) -> Self:
        """If no URL is set, keep the database on local disk (not a UNC share)."""
        if self.db_url.strip():
            return self
        path = self.runtime_dir() / "ledger.db"
        self.db_url = f"sqlite:///{path.as_posix()}"
        return self

    @property
    def schema_path(self) -> Path:
        """Absolute path to ``db/schema.sql`` (written in Phase 1)."""
        return PROJECT_ROOT / "db" / "schema.sql"

    def runtime_dir(self) -> Path:
        """Local directory for the SQLite file and other runtime artifacts."""
        if self.data_dir:
            return Path(self.data_dir).expanduser()
        return platform_data_dir()

    def resolved_db_path(self) -> Path | None:
        """Filesystem path of the SQLite database, or ``None`` for other backends."""
        prefix = "sqlite:///"
        if not self.db_url.startswith(prefix):
            return None
        raw = self.db_url[len(prefix) :]
        path = Path(raw)
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
