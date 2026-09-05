"""Ledger — SBIR/STTR award operations (contracts, labor costing, time).

Subpackages follow ``docs/BUILD_PLAN.md``:

* ``config``  — environment / ``.env`` settings
* ``db``      — engine/session plumbing (schema in Phase 1)
* ``models``  — SQLAlchemy models mirroring ``db/schema.sql`` (Phase 1)
* ``schemas`` — Pydantic v2 request/row schemas (Phase 1)
* ``api``     — FastAPI application
"""

from ledger.config import Settings, get_settings

__version__ = "0.1.0"

__all__ = ["Settings", "__version__", "get_settings"]
