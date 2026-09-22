#!/usr/bin/env python3
"""Task runner for Ledger: ``install``, ``lint``, ``test``, ``build-ui``, ``pack``, ``run``, ``db-init``, ``backup``.

Stdlib-only so it works before dependencies are installed, and on Windows where
``make`` is typically unavailable. The ``Makefile`` delegates here, so
``make lint`` and ``python tasks.py lint`` do the same thing.

Usage::

    python tasks.py lint
    python tasks.py test
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
API_HOST = "127.0.0.1"
API_PORT = "8000"


def _run(command: Sequence[str], *, cwd: Path | None = None) -> int:
    """Run a command, echoing it first."""
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.call(list(command), cwd=str(cwd or PROJECT_ROOT))


def _run_all(commands: Sequence[Sequence[str]]) -> int:
    """Run commands in order, stopping at the first failure."""
    for command in commands:
        code = _run(command)
        if code != 0:
            return code
    return 0


def _python(*args: str) -> list[str]:
    """Build a command invoking the current interpreter."""
    return [sys.executable, *args]


def _is_installed(module: str) -> bool:
    """Report whether an import name is available in the current interpreter."""
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _pip(*args: str) -> list[str]:
    """Build a pip command that can also reach public PyPI.

    This machine's default index is a corporate Artifactory that does not
    publish setuptools (and may omit other build deps). Public PyPI is an
    extra index, not a replacement.
    """
    return _python(
        "-m",
        "pip",
        *args,
        "--extra-index-url",
        "https://pypi.org/simple",
        "--trusted-host",
        "pypi.org",
        "--trusted-host",
        "files.pythonhosted.org",
    )


def task_install() -> int:
    """Install the project in editable mode with development extras."""
    return _run_all(
        [
            _pip("install", "--upgrade", "pip"),
            _pip("install", "setuptools>=68", "wheel"),
            _pip("install", "--no-build-isolation", "-e", ".[dev]"),
        ]
    )


def task_lint() -> int:
    """Check formatting and lint rules (ruff, then black)."""
    return _run_all(
        [
            _python("-m", "ruff", "check", "."),
            _python("-m", "black", "--check", "."),
        ]
    )


def task_format() -> int:
    """Apply ruff autofixes and black formatting in place."""
    return _run_all(
        [
            _python("-m", "ruff", "check", "--fix", "."),
            _python("-m", "black", "."),
        ]
    )


def task_test() -> int:
    """Run the pytest suite."""
    return _run(_python("-m", "pytest"))


def _guess_lan_ipv4() -> str | None:
    """Best-effort LAN address for the share URL printed at startup."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def task_build_ui() -> int:
    """Build the React app into ``web/dist`` for FastAPI to serve (D28)."""
    web = PROJECT_ROOT / "web"
    npm = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")
    if npm is None:
        npm = shutil.which("npm")
    if npm is None:
        print("npm is not on PATH. Install Node.js to build the UI.", file=sys.stderr)
        return 1
    if not (web / "package.json").is_file():
        print("web/package.json is missing.", file=sys.stderr)
        return 1
    return _run([npm, "run", "build"], cwd=web)


PACK_ROOT_FILES = (
    "pyproject.toml",
    "tasks.py",
    "alembic.ini",
    ".env.example",
)
PACK_ROOT_DIRS = ("src", "db", "alembic")
PACK_OUTPUT_NAME = "ledger-team"


def pack_output_dir(root: Path | None = None) -> Path:
    """Folder written by ``python tasks.py pack`` (gitignored under ``dist/``)."""
    return (root or PROJECT_ROOT) / "dist" / PACK_OUTPUT_NAME


def copy_team_bundle(dest: Path, *, root: Path | None = None) -> Path:
    """Copy a runnable team-lead tree into ``dest``. Requires ``web/dist``."""
    source = root or PROJECT_ROOT
    web_index = source / "web" / "dist" / "index.html"
    if not web_index.is_file():
        raise FileNotFoundError("web/dist is missing. Run python tasks.py build-ui, then pack.")
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for name in PACK_ROOT_FILES:
        src = source / name
        if not src.is_file():
            raise FileNotFoundError(f"missing {src}")
        shutil.copy2(src, dest / name)
    for name in PACK_ROOT_DIRS:
        src = source / name
        if not src.is_dir():
            raise FileNotFoundError(f"missing {src}")
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            src,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
    web_dest = dest / "web" / "dist"
    if web_dest.exists():
        shutil.rmtree(web_dest)
    shutil.copytree(source / "web" / "dist", web_dest)
    shutil.copy2(source / "pack" / "start-ledger.bat", dest / "start-ledger.bat")
    shutil.copy2(source / "pack" / "start-ledger.sh", dest / "start-ledger.sh")
    shutil.copy2(source / "pack" / "prepare_instance.py", dest / "prepare_instance.py")
    shutil.copy2(source / "pack" / "TEAM.md", dest / "README.md")
    return dest


def task_pack() -> int:
    """Assemble ``dist/ledger-team`` for another team lead (D8/D28)."""
    dest = pack_output_dir()
    try:
        copy_team_bundle(dest)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"pack: {dest}", flush=True)
    print("Zip that folder and give it to one team lead. Do not merge databases.")
    return 0


def task_run() -> int:
    """Serve the FastAPI application with uvicorn."""
    if not _is_installed("ledger.api.main"):
        print("The API application is missing (src/ledger/api/main.py).", file=sys.stderr)
        return 1
    from ledger.api.spa import DEFAULT_WEB_DIST
    from ledger.config import (
        get_settings,
        is_loopback_host,
        lan_bind_blocked_by_default_secret,
    )

    settings = get_settings()
    host = settings.api_host or API_HOST
    port = str(settings.api_port or API_PORT)
    if lan_bind_blocked_by_default_secret(host, settings.secret_key):
        print(
            "Refusing to bind beyond loopback while LEDGER_SECRET_KEY is the shipped default.",
            file=sys.stderr,
        )
        print("Set LEDGER_SECRET_KEY in .env, then retry.", file=sys.stderr)
        return 1
    if not (DEFAULT_WEB_DIST / "index.html").is_file():
        print(
            "warning: web/dist is missing. Run python tasks.py build-ui "
            "(or use Vite on :5173). /docs still works.",
            file=sys.stderr,
        )
    if not is_loopback_host(host):
        lan = _guess_lan_ipv4()
        share = f"http://{lan}:{port}" if lan else f"http://<this-computer>:{port}"
        print(f"LAN bind {host}:{port}. Teammates open {share}", flush=True)
    command = _python("-m", "uvicorn", "ledger.api.main:app", "--host", host, "--port", port)
    if is_loopback_host(host):
        command = _python(
            "-m",
            "uvicorn",
            "ledger.api.main:app",
            "--reload",
            "--host",
            host,
            "--port",
            port,
        )
    return _run(command)


def task_db_init() -> int:
    """Create the local data directory; apply ``db/schema.sql`` when it exists."""
    if not _is_installed("ledger.db.bootstrap"):
        print(
            "Database bootstrap is not implemented yet (docs/BUILD_PLAN.md Phase 1).",
            file=sys.stderr,
        )
        return 1
    return _run(_python("-m", "ledger.db.bootstrap"))


def task_backup() -> int:
    """Copy the SQLite file into the local data dir backups folder (D21)."""
    if not _is_installed("ledger.backup"):
        print("Backup is not implemented yet (docs/BUILD_PLAN.md Phase 2.5).", file=sys.stderr)
        return 1
    from ledger.backup import backup_sqlite

    try:
        path = backup_sqlite()
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"backup: {path}", flush=True)
    return 0


TASKS = {
    "install": task_install,
    "lint": task_lint,
    "format": task_format,
    "test": task_test,
    "build-ui": task_build_ui,
    "run": task_run,
    "db-init": task_db_init,
    "backup": task_backup,
    "pack": task_pack,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch the requested task and return its exit code."""
    parser = argparse.ArgumentParser(prog="tasks.py", description=__doc__.splitlines()[0])
    parser.add_argument("task", choices=sorted(TASKS), help="task to run")
    args = parser.parse_args(argv)
    return TASKS[args.task]()


if __name__ == "__main__":
    raise SystemExit(main())
