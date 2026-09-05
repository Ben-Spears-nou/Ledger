"""D28: FastAPI serves the built SPA on HTML navigation; JSON still hits the API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from tests.conftest import login

from ledger.api.main import create_app


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Ledger SPA</title>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ledger');", encoding="utf-8")
    return dist


def test_missing_dist_leaves_root_and_login_as_api_404(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dist=tmp_path / "missing"))
    assert client.get("/").status_code == 404
    assert client.get("/login", headers={"Accept": "text/html"}).status_code == 404


def test_html_navigation_gets_spa_json_still_hits_api(tmp_path: Path, isolated_db: Path) -> None:
    client = TestClient(create_app(web_dist=_dist(tmp_path)))
    html = {"Accept": "text/html"}
    page = client.get("/login", headers=html)
    assert page.status_code == 200
    assert "Ledger SPA" in page.text
    home = client.get("/", headers=html)
    assert home.status_code == 200
    assert "Ledger SPA" in home.text
    award_page = client.get("/awards/1", headers=html)
    assert award_page.status_code == 200
    assert "Ledger SPA" in award_page.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": "0.1.0"}

    listed = client.get("/awards", headers={"Accept": "application/json"})
    assert listed.status_code == 401

    token = login(client)
    listed_ok = client.get(
        "/awards",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    assert listed_ok.status_code == 200
    assert isinstance(listed_ok.json(), list)

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "ledger" in asset.text
