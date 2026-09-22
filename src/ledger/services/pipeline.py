"""Pipeline forecast nodes (D32). Never remaining-to-spend."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledger.models import Award
from ledger.models.pipeline import PipelineKind, PipelineNode
from ledger.schemas.pipeline import PipelineCreate, PipelineOut, PipelinePatch
from ledger.services.audit import record_event


class PipelineError(ValueError):
    """Domain error turned into HTTP 400/404 by the API."""


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise PipelineError(f"{field} must be YYYY-MM-DD") from exc


def serialize_pipeline(row: PipelineNode, award: Award | None = None) -> PipelineOut:
    """Forecast DTO with optional award short code."""
    return PipelineOut(
        pipeline_node_id=row.pipeline_node_id,
        award_id=row.award_id,
        award_short_code=award.short_code if award is not None else None,
        kind_code=row.kind_code,
        title=row.title,
        amount_cents=row.amount_cents,
        expected_date=row.expected_date,
        notes=row.notes,
        created_at=row.created_at,
    )


def require_award(session: Session, award_id: int) -> Award:
    """Load an award or raise."""
    award = session.get(Award, award_id)
    if award is None:
        raise PipelineError("award not found")
    return award


def pipeline_cents_for(session: Session, award_id: int) -> int:
    """Sum of forecast cents on one award (not remaining)."""
    value = session.scalar(
        select(func.coalesce(func.sum(PipelineNode.amount_cents), 0)).where(
            PipelineNode.award_id == award_id
        )
    )
    return int(value or 0)


def list_pipeline(
    session: Session,
    *,
    award_id: int | None = None,
) -> list[tuple[PipelineNode, Award]]:
    """Forecast rows with awards, newest last."""
    stmt = (
        select(PipelineNode, Award)
        .join(Award, Award.award_id == PipelineNode.award_id)
        .order_by(PipelineNode.pipeline_node_id)
    )
    if award_id is not None:
        stmt = stmt.where(PipelineNode.award_id == award_id)
    return list(session.execute(stmt).all())


def create_pipeline(
    session: Session,
    award: Award,
    payload: PipelineCreate,
    *,
    actor_id: int | None,
) -> PipelineNode:
    """Insert a forecast node. Closed awards are rejected."""
    if award.status_code == "closed":
        raise PipelineError("closed awards cannot take pipeline nodes")
    kind = session.get(PipelineKind, payload.kind_code)
    if kind is None:
        raise PipelineError("unknown pipeline kind")
    title = payload.title.strip()
    if not title:
        raise PipelineError("title is required")
    expected = None
    if payload.expected_date:
        expected = _iso_date(payload.expected_date, field="expected_date")
    row = PipelineNode(
        award_id=award.award_id,
        kind_code=payload.kind_code,
        title=title,
        amount_cents=payload.amount_cents,
        expected_date=expected,
        notes=payload.notes,
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        action="pipeline_create",
        entity_type="pipeline_node",
        entity_id=row.pipeline_node_id,
        actor_user_id=actor_id,
        detail={"award_id": award.award_id, "amount_cents": row.amount_cents},
    )
    return row


def patch_pipeline(
    session: Session,
    row: PipelineNode,
    payload: PipelinePatch,
    *,
    actor_id: int | None,
) -> PipelineNode:
    """Update forecast fields."""
    data = payload.model_dump(exclude_unset=True)
    if "kind_code" in data and data["kind_code"] is not None:
        kind = session.get(PipelineKind, data["kind_code"])
        if kind is None:
            raise PipelineError("unknown pipeline kind")
        row.kind_code = data["kind_code"]
    if "title" in data and data["title"] is not None:
        title = data["title"].strip()
        if not title:
            raise PipelineError("title is required")
        row.title = title
    if "amount_cents" in data and data["amount_cents"] is not None:
        row.amount_cents = data["amount_cents"]
    if "expected_date" in data:
        if data["expected_date"]:
            row.expected_date = _iso_date(data["expected_date"], field="expected_date")
        else:
            row.expected_date = None
    if "notes" in data:
        row.notes = data["notes"]
    session.flush()
    record_event(
        session,
        action="pipeline_update",
        entity_type="pipeline_node",
        entity_id=row.pipeline_node_id,
        actor_user_id=actor_id,
        detail={"amount_cents": row.amount_cents},
    )
    return row


def delete_pipeline(
    session: Session,
    row: PipelineNode,
    *,
    actor_id: int | None,
) -> None:
    """Remove a forecast row."""
    node_id = row.pipeline_node_id
    award_id = row.award_id
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="pipeline_delete",
        entity_type="pipeline_node",
        entity_id=node_id,
        actor_user_id=actor_id,
        detail={"award_id": award_id},
    )
