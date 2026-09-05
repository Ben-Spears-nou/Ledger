"""FastAPI application.

Served as ``uvicorn ledger.api.main:app``. Interactive docs live at ``/docs``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledger import __version__
from ledger.api.routers import audit, auth, awards, lookups, people
from ledger.api.routers.commitments import (
    award_commitments_router,
    commitments_router,
    instruments_router,
    purchases_router,
    travel_router,
)
from ledger.api.routers.schedule import (
    assignments_router,
    award_tasks_router,
    capacity_router,
    tasks_router,
)
from ledger.api.routers.time import approvals_router, me_router, rates_router
from ledger.api.spa import DEFAULT_WEB_DIST, install_spa
from ledger.config import DEFAULT_SECRET_KEY, get_settings

_LOCAL_UI_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)

logger = logging.getLogger("ledger")


def warn_if_default_secret() -> None:
    """Log when the shipped HMAC secret is still in use. Do not crash tests."""
    if get_settings().secret_key == DEFAULT_SECRET_KEY:
        logger.warning("LEDGER_SECRET_KEY is the shipped default; set a new value before sharing.")


def create_app(web_dist: Path | None = None) -> FastAPI:
    """Build the Ledger API. ``web_dist`` defaults to ``web/dist`` (D28)."""
    warn_if_default_secret()
    application = FastAPI(
        title="Ledger",
        description="SBIR/STTR award operations. Not the official accounting book.",
        version=__version__,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(_LOCAL_UI_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth.router)
    application.include_router(lookups.router)
    application.include_router(people.router)
    application.include_router(rates_router)
    application.include_router(awards.router)
    application.include_router(award_tasks_router)
    application.include_router(tasks_router)
    application.include_router(assignments_router)
    application.include_router(capacity_router)
    application.include_router(purchases_router)
    application.include_router(travel_router)
    application.include_router(commitments_router)
    application.include_router(instruments_router)
    application.include_router(award_commitments_router)
    application.include_router(me_router)
    application.include_router(approvals_router)
    application.include_router(audit.router)

    @application.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    install_spa(application, DEFAULT_WEB_DIST if web_dist is None else web_dist)
    return application


app = create_app()
