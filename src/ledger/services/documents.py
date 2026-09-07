"""Document register and local-disk files; compliance due dates (D29–D31)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.config import get_settings
from ledger.models import Award
from ledger.models.documents import (
    ComplianceItem,
    ComplianceKind,
    ComplianceStatus,
    Document,
    DocumentKind,
)
from ledger.schemas.documents import (
    ComplianceCreate,
    ComplianceOut,
    CompliancePatch,
    DocumentCreate,
    DocumentOut,
)
from ledger.services.audit import record_event

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = frozenset(
    {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".zip"}
)


class DocumentError(ValueError):
    """Domain error turned into HTTP 400/404/409 by the API."""


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise DocumentError(f"{field} must be YYYY-MM-DD") from exc


def serialize_document(row: Document) -> DocumentOut:
    """Metadata DTO."""
    return DocumentOut(
        document_id=row.document_id,
        award_id=row.award_id,
        kind_code=row.kind_code,
        title=row.title,
        document_date=row.document_date,
        notes=row.notes,
        original_filename=row.original_filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        has_file=bool(row.stored_ext),
        created_at=row.created_at,
    )


def serialize_compliance(row: ComplianceItem, award: Award | None = None) -> ComplianceOut:
    """Compliance DTO with optional award short code for the calendar."""
    return ComplianceOut(
        compliance_item_id=row.compliance_item_id,
        award_id=row.award_id,
        award_short_code=award.short_code if award is not None else None,
        kind_code=row.kind_code,
        title=row.title,
        due_date=row.due_date,
        status_code=row.status_code,
        notes=row.notes,
        completed_at=row.completed_at,
        document_id=row.document_id,
        created_at=row.created_at,
    )


def require_award(session: Session, award_id: int) -> Award:
    """Load an award or raise."""
    award = session.get(Award, award_id)
    if award is None:
        raise DocumentError("award not found")
    return award


def list_documents(session: Session, award_id: int) -> list[Document]:
    """Documents for one award, newest id last."""
    return list(
        session.scalars(
            select(Document).where(Document.award_id == award_id).order_by(Document.document_id)
        )
    )


def create_document(
    session: Session,
    award: Award,
    payload: DocumentCreate,
    *,
    actor_id: int | None,
) -> Document:
    """Insert a register row. File is a later POST."""
    kind = session.get(DocumentKind, payload.kind_code)
    if kind is None:
        raise DocumentError("unknown document kind")
    title = payload.title.strip()
    if not title:
        raise DocumentError("title is required")
    doc_date = None
    if payload.document_date:
        doc_date = _iso_date(payload.document_date, field="document_date")
    row = Document(
        award_id=award.award_id,
        kind_code=payload.kind_code,
        title=title,
        document_date=doc_date,
        notes=payload.notes,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="document_create",
        entity_type="document",
        entity_id=row.document_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id, "kind_code": row.kind_code},
    )
    return row


def stored_path(row: Document) -> Path | None:
    """Absolute path of a stored file, or None."""
    if not row.stored_ext:
        return None
    return (
        get_settings().runtime_dir()
        / "documents"
        / str(row.award_id)
        / f"{row.document_id}{row.stored_ext}"
    )


def attach_file(
    session: Session,
    row: Document,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    actor_id: int | None,
) -> Document:
    """Write bytes to the data dir. One file per document (D29)."""
    if row.stored_ext:
        raise DocumentError("document already has a file")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentError("file is larger than 20 MiB")
    if not data:
        raise DocumentError("file is empty")
    suffix = Path(filename.replace("\\", "/")).name
    suffix = Path(suffix).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentError("file type is not allowed")
    original = Path(filename.replace("\\", "/")).name
    directory = get_settings().runtime_dir() / "documents" / str(row.award_id)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{row.document_id}{suffix}"
    dest.write_bytes(data)
    row.original_filename = original
    row.stored_ext = suffix
    row.content_type = content_type or "application/octet-stream"
    row.size_bytes = len(data)
    session.flush()
    record_event(
        session,
        action="document_file",
        entity_type="document",
        entity_id=row.document_id,
        actor_user_id=actor_id,
        detail={"filename": original, "size_bytes": row.size_bytes},
    )
    return row


def list_compliance(
    session: Session,
    *,
    award_id: int | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
    status_code: str | None = None,
) -> list[tuple[ComplianceItem, Award]]:
    """Compliance rows with awards, ordered by due date."""
    stmt = (
        select(ComplianceItem, Award)
        .join(Award, Award.award_id == ComplianceItem.award_id)
        .order_by(ComplianceItem.due_date, ComplianceItem.compliance_item_id)
    )
    if award_id is not None:
        stmt = stmt.where(ComplianceItem.award_id == award_id)
    if due_from:
        stmt = stmt.where(ComplianceItem.due_date >= _iso_date(due_from, field="due_from"))
    if due_to:
        stmt = stmt.where(ComplianceItem.due_date <= _iso_date(due_to, field="due_to"))
    if status_code:
        stmt = stmt.where(ComplianceItem.status_code == status_code)
    return list(session.execute(stmt).all())


def create_compliance(
    session: Session,
    award: Award,
    payload: ComplianceCreate,
    *,
    actor_id: int | None,
) -> ComplianceItem:
    """Insert an open compliance item."""
    kind = session.get(ComplianceKind, payload.kind_code)
    if kind is None:
        raise DocumentError("unknown compliance kind")
    title = payload.title.strip()
    if not title:
        raise DocumentError("title is required")
    row = ComplianceItem(
        award_id=award.award_id,
        kind_code=payload.kind_code,
        title=title,
        due_date=_iso_date(payload.due_date, field="due_date"),
        status_code="open",
        notes=payload.notes,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="compliance_create",
        entity_type="compliance_item",
        entity_id=row.compliance_item_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id, "due_date": row.due_date},
    )
    return row


def patch_compliance(
    session: Session,
    row: ComplianceItem,
    payload: CompliancePatch,
    *,
    actor_id: int | None,
) -> ComplianceItem:
    """Update status and/or notes."""
    data = payload.model_dump(exclude_unset=True)
    if "notes" in data:
        row.notes = data["notes"]
    if "status_code" in data:
        status = session.get(ComplianceStatus, data["status_code"])
        if status is None:
            raise DocumentError("unknown compliance status")
        row.status_code = data["status_code"]
        if data["status_code"] == "done":
            row.completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        else:
            row.completed_at = None
    if "document_id" in data:
        document_id = data["document_id"]
        if document_id is None:
            row.document_id = None
        else:
            document = session.get(Document, document_id)
            if document is None or document.award_id != row.award_id:
                raise DocumentError("document not found on this award")
            row.document_id = document_id
    session.flush()
    record_event(
        session,
        action="compliance_status",
        entity_type="compliance_item",
        entity_id=row.compliance_item_id,
        actor_user_id=actor_id,
        detail={"status_code": row.status_code},
    )
    return row


def delete_document(session: Session, row: Document, *, actor_id: int | None) -> None:
    """Remove an unlinked document and its file (D45)."""
    linked = session.scalar(
        select(ComplianceItem.compliance_item_id)
        .where(ComplianceItem.document_id == row.document_id)
        .limit(1)
    )
    if linked is not None:
        raise DocumentError("cannot delete a document linked from compliance")
    path = stored_path(row)
    if path is not None and path.is_file():
        path.unlink()
    document_id = row.document_id
    award_id = row.award_id
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="document_delete",
        entity_type="document",
        entity_id=document_id,
        actor_user_id=actor_id,
        detail={"award_id": award_id},
    )


def delete_compliance(session: Session, row: ComplianceItem, *, actor_id: int | None) -> None:
    """Remove an open due date (D45)."""
    if row.status_code != "open":
        raise DocumentError("cannot delete a completed compliance item")
    item_id = row.compliance_item_id
    award_id = row.award_id
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="compliance_delete",
        entity_type="compliance_item",
        entity_id=item_id,
        actor_user_id=actor_id,
        detail={"award_id": award_id},
    )
