"""Serve the built React UI from the same origin as the API (D28)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.types import ASGIApp

from ledger.config import PROJECT_ROOT

DEFAULT_WEB_DIST = PROJECT_ROOT / "web" / "dist"

_SKIP_SPA_PREFIXES = ("/docs", "/redoc")
_SKIP_SPA_PATHS = frozenset({"/openapi.json", "/health"})


def wants_html(request: Request) -> bool:
    """True when the client asked for a document, not JSON."""
    return "text/html" in request.headers.get("accept", "").lower()


def safe_dist_file(dist: Path, url_path: str) -> Path | None:
    """Return a file under ``dist`` for ``url_path``, or None."""
    relative = url_path.lstrip("/")
    if not relative or any(part == ".." for part in Path(relative).parts):
        return None
    candidate = dist.joinpath(*Path(relative).parts)
    try:
        resolved = candidate.resolve()
        resolved.relative_to(dist.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def index_response(index: Path) -> FileResponse:
    """HTML shell; hashed assets can still be cached by the browser."""
    return FileResponse(
        index,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


class SpaHtmlMiddleware(BaseHTTPMiddleware):
    """HTML navigation gets index.html; JSON fetch still hits API routes."""

    def __init__(self, app: ASGIApp, dist: Path) -> None:
        super().__init__(app)
        self.dist = dist
        self.index = dist / "index.html"

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in {"GET", "HEAD"} or not self.index.is_file():
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _SKIP_SPA_PREFIXES) or path in _SKIP_SPA_PATHS:
            return await call_next(request)
        if path == "/":
            return index_response(self.index)
        existing = safe_dist_file(self.dist, path)
        if existing is not None:
            return FileResponse(existing)
        if wants_html(request):
            return index_response(self.index)
        return await call_next(request)


def install_spa(application: FastAPI, dist: Path) -> None:
    """HTML navigation is served from ``dist`` when index.html exists."""
    application.add_middleware(SpaHtmlMiddleware, dist=dist)
