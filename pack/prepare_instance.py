#!/usr/bin/env python3
"""First-run helper for a team-lead copy of Ledger.

Creates ``.env`` from ``.env.example`` with a unique ``LEDGER_SECRET_KEY``
when ``.env`` is missing. Never overwrites an existing ``.env``.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

DEFAULT_SECRET = "dev-only-change-me"


def instance_root() -> Path:
    """Directory that contains ``pyproject.toml`` (repo or packed copy)."""
    here = Path(__file__).resolve().parent
    if (here / "pyproject.toml").is_file():
        return here
    parent = here.parent
    if (parent / "pyproject.toml").is_file():
        return parent
    return here


def write_env_if_missing(root: Path) -> Path:
    """Copy ``.env.example`` to ``.env`` and replace the shipped secret."""
    env_path = root / ".env"
    example = root / ".env.example"
    if env_path.is_file():
        return env_path
    if not example.is_file():
        raise FileNotFoundError(f"missing {example}")
    text = example.read_text(encoding="utf-8")
    secret = secrets.token_urlsafe(32)
    if f"LEDGER_SECRET_KEY={DEFAULT_SECRET}" in text:
        text = text.replace(
            f"LEDGER_SECRET_KEY={DEFAULT_SECRET}",
            f"LEDGER_SECRET_KEY={secret}",
            1,
        )
    else:
        text = text.rstrip() + f"\nLEDGER_SECRET_KEY={secret}\n"
    env_path.write_text(text, encoding="utf-8")
    return env_path


def env_secret(env_path: Path) -> str | None:
    """Return LEDGER_SECRET_KEY from a dotenv file, if present."""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("LEDGER_SECRET_KEY="):
            return stripped.split("=", 1)[1]
    return None


def dist_ok(root: Path) -> bool:
    """True when FastAPI can serve the built website."""
    return (root / "web" / "dist" / "index.html").is_file()


def main(argv: list[str] | None = None) -> int:
    """Create ``.env`` on first run and print readiness notes."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="instance root (default: directory of this script or its parent)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else instance_root()
    try:
        env_path = write_env_if_missing(root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    secret = env_secret(env_path)
    if secret == DEFAULT_SECRET:
        print(
            "warning: LEDGER_SECRET_KEY is still the shipped default. "
            "Change it in .env before setting LEDGER_API_HOST=0.0.0.0.",
            file=sys.stderr,
        )
    if not dist_ok(root):
        print(
            "warning: web/dist is missing. On the machine that has Node, "
            "run: python tasks.py build-ui",
            file=sys.stderr,
        )
    data = os.environ.get("LEDGER_DATA_DIR") or (
        Path(os.environ["LOCALAPPDATA"]) / "ledger"
        if os.name == "nt" and os.environ.get("LOCALAPPDATA")
        else Path.home() / ".local" / "share" / "ledger"
    )
    print(f"instance: {root}", flush=True)
    print(f"env: {env_path}", flush=True)
    print(f"sqlite (default): {data}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
