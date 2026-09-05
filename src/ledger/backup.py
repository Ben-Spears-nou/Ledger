"""Copy the SQLite file into the local data dir (D21). Not a product."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from ledger.config import get_settings


def backup_sqlite(*, dest_dir: Path | None = None, source: Path | None = None) -> Path:
    """Copy the configured SQLite database to ``data-dir/backups/`` with a stamp."""
    settings = get_settings()
    src = source or settings.resolved_db_path()
    if src is None:
        raise RuntimeError("backup only supports a SQLite file (LEDGER_DB_URL)")
    if not src.is_file():
        raise FileNotFoundError(f"database file not found: {src}")
    target_dir = dest_dir or (settings.runtime_dir() / "backups")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = target_dir / f"ledger-{stamp}.db"
    if dest.exists():
        dest = target_dir / f"ledger-{stamp}-{src.stat().st_mtime_ns}.db"
    shutil.copy2(src, dest)
    if dest.stat().st_size <= 0:
        raise RuntimeError(f"backup was empty: {dest}")
    return dest
