"""Admin document register, file upload/download, and compliance dates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ledger.api.deps import get_db, require_admin
from ledger.models import UserAccount
from ledger.models.documents import ComplianceItem, Document
from ledger.schemas.documents import (
    ComplianceCreate,
    ComplianceOut,
    CompliancePatch,
    DocumentCreate,
    DocumentOut,
)
from ledger.services.documents import (
    DocumentError,
    attach_file,
    create_compliance,
    create_document,
    delete_compliance,
    delete_document,
    list_compliance,
    list_documents,
    patch_compliance,
    require_award,
    serialize_compliance,
    serialize_document,
    stored_path,
)

award_documents_router = APIRouter(prefix="/awards", tags=["documents"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])
award_compliance_router = APIRouter(prefix="/awards", tags=["compliance"])
compliance_router = APIRouter(prefix="/compliance", tags=["compliance"])


def _http(exc: DocumentError, *, not_found: bool = False) -> HTTPException:
    message = str(exc)
    missing = {"award not found", "document not found", "compliance item not found"}
    if not_found or message in missing:
        return HTTPException(status.HTTP_404_NOT_FOUND, message)
    if "already has a file" in message or "cannot delete" in message:
        return HTTPException(status.HTTP_409_CONFLICT, message)
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


@award_documents_router.get("/{award_id}/documents", response_model=list[DocumentOut])
def get_award_documents(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[DocumentOut]:
    """List document metadata for an award."""
    try:
        require_award(session, award_id)
    except DocumentError as exc:
        raise _http(exc, not_found=True) from exc
    return [serialize_document(row) for row in list_documents(session, award_id)]


@award_documents_router.post(
    "/{award_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def post_award_document(
    award_id: int,
    payload: DocumentCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> DocumentOut:
    """Create a register row (file optional later)."""
    try:
        award = require_award(session, award_id)
        row = create_document(session, award, payload, actor_id=admin.user_account_id)
    except DocumentError as exc:
        raise _http(exc, not_found=str(exc) == "award not found") from exc
    return serialize_document(row)


@documents_router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> DocumentOut:
    """One document's metadata."""
    row = session.get(Document, document_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return serialize_document(row)


@documents_router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> FileResponse:
    """Authenticated download of the stored file."""
    row = session.get(Document, document_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    path = stored_path(row)
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no file stored")
    return FileResponse(
        path,
        filename=row.original_filename or path.name,
        media_type=row.content_type or "application/octet-stream",
    )


@documents_router.post("/{document_id}/file", response_model=DocumentOut)
async def post_document_file(
    document_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> DocumentOut:
    """Attach a file to a register row."""
    row = session.get(Document, document_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    data = await file.read()
    try:
        row = attach_file(
            session,
            row,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            data=data,
            actor_id=admin.user_account_id,
        )
    except DocumentError as exc:
        raise _http(exc) from exc
    return serialize_document(row)


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an unlinked document and its file (D45)."""
    row = session.get(Document, document_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    try:
        delete_document(session, row, actor_id=admin.user_account_id)
    except DocumentError as exc:
        raise _http(exc) from exc


@award_compliance_router.get("/{award_id}/compliance", response_model=list[ComplianceOut])
def get_award_compliance(
    award_id: int,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[ComplianceOut]:
    """Due dates on one award."""
    try:
        award = require_award(session, award_id)
    except DocumentError as exc:
        raise _http(exc, not_found=True) from exc
    return [
        serialize_compliance(row, award)
        for row, _joined in list_compliance(session, award_id=award_id)
    ]


@award_compliance_router.post(
    "/{award_id}/compliance",
    response_model=ComplianceOut,
    status_code=status.HTTP_201_CREATED,
)
def post_award_compliance(
    award_id: int,
    payload: ComplianceCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ComplianceOut:
    """Add an open compliance item."""
    try:
        award = require_award(session, award_id)
        row = create_compliance(session, award, payload, actor_id=admin.user_account_id)
    except DocumentError as exc:
        raise _http(exc, not_found=str(exc) == "award not found") from exc
    return serialize_compliance(row, award)


@compliance_router.get("", response_model=list[ComplianceOut])
def get_compliance_calendar(
    due_from: str | None = Query(default=None),
    due_to: str | None = Query(default=None),
    status_code: str | None = Query(default=None),
    award_id: int | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[ComplianceOut]:
    """Due dates across awards (calendar)."""
    try:
        rows = list_compliance(
            session,
            award_id=award_id,
            due_from=due_from,
            due_to=due_to,
            status_code=status_code,
        )
    except DocumentError as exc:
        raise _http(exc) from exc
    return [serialize_compliance(item, award) for item, award in rows]


@compliance_router.patch("/{compliance_item_id}", response_model=ComplianceOut)
def patch_compliance_item(
    compliance_item_id: int,
    payload: CompliancePatch,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> ComplianceOut:
    """Mark done/waived or edit notes."""
    row = session.get(ComplianceItem, compliance_item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "compliance item not found")
    try:
        row = patch_compliance(session, row, payload, actor_id=admin.user_account_id)
    except DocumentError as exc:
        raise _http(exc) from exc
    award = require_award(session, row.award_id)
    return serialize_compliance(row, award)


@compliance_router.delete("/{compliance_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_compliance_item(
    compliance_item_id: int,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> None:
    """Delete an open due date (D45)."""
    row = session.get(ComplianceItem, compliance_item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "compliance item not found")
    try:
        delete_compliance(session, row, actor_id=admin.user_account_id)
    except DocumentError as exc:
        raise _http(exc) from exc
