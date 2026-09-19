"""Team-lead folder layout: first-run ``.env`` and ``tasks.py pack``."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import tasks

ROOT = Path(__file__).resolve().parents[1]


def _prepare():
    spec = importlib.util.spec_from_file_location(
        "prepare_instance", ROOT / "pack" / "prepare_instance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mini_source(tmp: Path) -> Path:
    """Enough of a tree for ``copy_team_bundle`` without the real UI source."""
    (tmp / "src" / "ledger").mkdir(parents=True)
    (tmp / "src" / "ledger" / "__init__.py").write_text("", encoding="utf-8")
    (tmp / "db").mkdir()
    (tmp / "db" / "schema.sql").write_text("-- test\n", encoding="utf-8")
    (tmp / "alembic").mkdir()
    (tmp / "alembic" / "README").write_text("x\n", encoding="utf-8")
    (tmp / "pack").mkdir()
    for name in ("start-ledger.bat", "start-ledger.sh", "prepare_instance.py", "TEAM.md"):
        text = (ROOT / "pack" / name).read_text(encoding="utf-8")
        (tmp / "pack" / name).write_text(text, encoding="utf-8")
    (tmp / "web" / "dist").mkdir(parents=True)
    (tmp / "web" / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    for name in ("pyproject.toml", "tasks.py", "alembic.ini", ".env.example"):
        (tmp / name).write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp


def test_prepare_writes_env_once(tmp_path: Path) -> None:
    prepare = _prepare()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    (tmp_path / ".env.example").write_text(example, encoding="utf-8")
    first = prepare.write_env_if_missing(tmp_path)
    secret = prepare.env_secret(first)
    assert secret
    assert secret != prepare.DEFAULT_SECRET
    first.write_text("LEDGER_SECRET_KEY=keep-me\n", encoding="utf-8")
    prepare.write_env_if_missing(tmp_path)
    assert prepare.env_secret(first) == "keep-me"


def test_prepare_cli_warns_without_dist(tmp_path: Path, capsys) -> None:
    prepare = _prepare()
    (tmp_path / ".env.example").write_text(
        "LEDGER_SECRET_KEY=dev-only-change-me\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert prepare.main(["--root", str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert "web/dist is missing" in err


def test_copy_team_bundle_requires_web_dist(tmp_path: Path) -> None:
    src = _mini_source(tmp_path / "src-tree")
    (src / "web" / "dist" / "index.html").unlink()
    dest = tmp_path / "out"
    try:
        tasks.copy_team_bundle(dest, root=src)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError as exc:
        assert "web/dist" in str(exc)


def test_copy_team_bundle_layout(tmp_path: Path) -> None:
    src = _mini_source(tmp_path / "src-tree")
    dest = tmp_path / "ledger-team"
    tasks.copy_team_bundle(dest, root=src)
    assert (dest / "start-ledger.bat").is_file()
    assert (dest / "prepare_instance.py").is_file()
    assert (dest / "README.md").read_text(encoding="utf-8").startswith("# Ledger")
    assert (dest / "web" / "dist" / "index.html").is_file()
    assert (dest / "src" / "ledger" / "__init__.py").is_file()
    assert not (dest / "web" / "src").exists()
    assert not (dest / "tests").exists()


def test_pack_task_registered() -> None:
    assert "pack" in tasks.TASKS
