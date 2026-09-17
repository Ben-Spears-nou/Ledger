"""SOW requirement extraction, progress maintenance, and work Gantt."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledger.models import Award, Document, WorkPlanItem
from ledger.schemas.work_plan import (
    WorkGanttBarOut,
    WorkGanttOut,
    WorkPlanConfirmIn,
    WorkPlanDraftIn,
    WorkPlanItemOut,
    WorkPlanMoveIn,
    WorkPlanPatch,
    WorkPlanProposeIn,
    WorkPlanProposeOut,
)
from ledger.services.audit import record_event
from ledger.services.contract_schedule import (
    _read_document_text,
    contract_pop_dates,
    require_award,
)

_REQUIREMENT_HEADING = re.compile(r"(?m)^\s*(\d+\.\d+)\s+([^\n]+?)\s*$")
_SECTION_START = re.compile(r"(?im)^\s*4\.0\s+REQUIREMENTS(?:\s*\(TASKS\))?.*$")
_SECTION_END = re.compile(r"(?im)^\s*5\.0\s+")


class WorkPlanError(ValueError):
    """Domain error for work-plan operations."""


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise WorkPlanError(f"{field} must be YYYY-MM-DD") from exc


def serialize_item(row: WorkPlanItem) -> WorkPlanItemOut:
    """API representation for a stored requirement."""
    return WorkPlanItemOut(
        work_plan_item_id=row.work_plan_item_id,
        award_id=row.award_id,
        requirement_code=row.requirement_code,
        title=row.title,
        start_date=row.start_date,
        due_date=row.due_date,
        percent_complete_bp=row.percent_complete_bp,
        notes=row.notes,
        source_document_id=row.source_document_id,
        origin_code=row.origin_code,
        sort_order=row.sort_order,
        created_at=row.created_at,
    )


def _next_sort_order(session: Session, award_id: int) -> int:
    """Place a new row after the last displayed requirement."""
    current = session.scalar(
        select(func.max(WorkPlanItem.sort_order)).where(WorkPlanItem.award_id == award_id)
    )
    return (current or 0) + 1


def _renormalize(session: Session, award_id: int) -> None:
    """Keep sort_order as 1..n in current display order."""
    for index, row in enumerate(list_items(session, award_id), start=1):
        row.sort_order = index
    session.flush()


def list_items(session: Session, award_id: int) -> list[WorkPlanItem]:
    """Work-plan rows in presentation order."""
    return list(
        session.scalars(
            select(WorkPlanItem)
            .where(WorkPlanItem.award_id == award_id)
            .order_by(WorkPlanItem.sort_order, WorkPlanItem.work_plan_item_id)
        )
    )


def extract_requirements(
    text: str,
    award: Award,
    *,
    source_document_id: int | None,
) -> list[WorkPlanItemOut]:
    """Extract top-level numbered SOW requirements and infer sequential windows."""
    start_match = _SECTION_START.search(text)
    section = text[start_match.end() :] if start_match else text
    end_match = _SECTION_END.search(section)
    if end_match:
        section = section[: end_match.start()]

    headings: list[tuple[str, str]] = []
    seen_codes: set[str] = set()
    for match in _REQUIREMENT_HEADING.finditer(section):
        code = match.group(1)
        title = " ".join(match.group(2).split())
        if code in seen_codes or not title:
            continue
        seen_codes.add(code)
        headings.append((code, title))
    if not headings:
        return []

    contract_pop = contract_pop_dates(text)
    work_start = contract_pop[0] if contract_pop else date.fromisoformat(award.pop_start)
    work_end = contract_pop[1] if contract_pop else date.fromisoformat(award.pop_end)
    span = (work_end - work_start).days
    found: list[WorkPlanItemOut] = []
    for index, (code, title) in enumerate(headings):
        start = work_start + (work_end - work_start) * index // len(headings)
        due = work_start + (work_end - work_start) * (index + 1) // len(headings)
        found.append(
            WorkPlanItemOut(
                award_id=award.award_id,
                requirement_code=code,
                title=title[:160],
                start_date=start.isoformat(),
                due_date=due.isoformat(),
                percent_complete_bp=0,
                notes=(
                    "Requirement extracted from SOW; start and due dates are evenly "
                    f"inferred across the {span}-day contract PoP. Review before confirming."
                ),
                source_document_id=source_document_id,
                origin_code="extract",
                sort_order=index + 1,
            )
        )
    return found


def propose(
    session: Session,
    award: Award,
    payload: WorkPlanProposeIn,
) -> WorkPlanProposeOut:
    """Build an editable work-plan draft without writing rows."""
    notes: list[str] = []
    items: list[WorkPlanItemOut] = []
    source_id = payload.document_id
    if source_id is not None:
        document = session.get(Document, source_id)
        if document is None or document.award_id != award.award_id:
            raise WorkPlanError("document not found on this award")
        text, skip = _read_document_text(document)
        if skip:
            notes.append(skip)
        elif text:
            items.extend(extract_requirements(text, award, source_document_id=source_id))
    pasted = (payload.text or "").strip()
    if pasted:
        items.extend(extract_requirements(pasted, award, source_document_id=source_id))
    if not items:
        notes.append("No numbered SOW requirements such as 4.1, 4.2, and 4.3 were found.")
    else:
        notes.append("Dates are inferred planning windows; edit them before confirming.")
    notes.append("Nothing is saved until you confirm the rows you want to keep.")
    return WorkPlanProposeOut(award_id=award.award_id, notes=notes, items=items)


def _insert(
    session: Session,
    award: Award,
    draft: WorkPlanDraftIn,
    *,
    actor_id: int | None,
) -> WorkPlanItem:
    title = draft.title.strip()
    if not title:
        raise WorkPlanError("title is required")
    start = _iso_date(draft.start_date, field="start_date")
    due = _iso_date(draft.due_date, field="due_date")
    if due < start:
        raise WorkPlanError("due_date must be on or after start_date")
    source_id = draft.source_document_id
    if source_id is not None:
        document = session.get(Document, source_id)
        if document is None or document.award_id != award.award_id:
            raise WorkPlanError("document not found on this award")
    row = WorkPlanItem(
        award_id=award.award_id,
        requirement_code=(draft.requirement_code or "").strip() or None,
        title=title,
        start_date=start,
        due_date=due,
        percent_complete_bp=draft.percent_complete_bp,
        notes=draft.notes,
        source_document_id=source_id,
        origin_code=draft.origin_code if draft.origin_code in {"extract", "manual"} else "manual",
        sort_order=(
            draft.sort_order if draft.sort_order > 0 else _next_sort_order(session, award.award_id)
        ),
        created_by=actor_id,
    )
    session.add(row)
    session.flush()
    return row


def confirm(
    session: Session,
    award: Award,
    payload: WorkPlanConfirmIn,
    *,
    actor_id: int | None,
) -> list[WorkPlanItem]:
    """Insert selected proposed requirements."""
    rows = [
        _insert(session, award, draft, actor_id=actor_id) for draft in payload.items if draft.keep
    ]
    record_event(
        session,
        action="work_plan_confirm",
        entity_type="work_plan_item",
        entity_id=award.award_id,
        actor_user_id=actor_id,
        detail={"count": len(rows)},
    )
    return rows


def create_item(
    session: Session,
    award: Award,
    draft: WorkPlanDraftIn,
    *,
    actor_id: int | None,
) -> WorkPlanItem:
    """Add one manual work-plan requirement."""
    draft.origin_code = "manual"
    row = _insert(session, award, draft, actor_id=actor_id)
    record_event(
        session,
        action="work_plan_create",
        entity_type="work_plan_item",
        entity_id=row.work_plan_item_id,
        actor_user_id=actor_id,
    )
    return row


def patch_item(
    session: Session,
    row: WorkPlanItem,
    payload: WorkPlanPatch,
    *,
    actor_id: int | None,
) -> WorkPlanItem:
    """Edit requirement, dates, ordering, or percent complete."""
    if payload.requirement_code is not None:
        row.requirement_code = payload.requirement_code.strip() or None
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise WorkPlanError("title is required")
        row.title = title
    if payload.start_date is not None:
        row.start_date = _iso_date(payload.start_date, field="start_date")
    if payload.due_date is not None:
        row.due_date = _iso_date(payload.due_date, field="due_date")
    if row.due_date < row.start_date:
        raise WorkPlanError("due_date must be on or after start_date")
    if payload.percent_complete_bp is not None:
        row.percent_complete_bp = payload.percent_complete_bp
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    session.flush()
    record_event(
        session,
        action="work_plan_update",
        entity_type="work_plan_item",
        entity_id=row.work_plan_item_id,
        actor_user_id=actor_id,
        detail={"percent_complete_bp": row.percent_complete_bp},
    )
    return row


def move_item(
    session: Session,
    row: WorkPlanItem,
    payload: WorkPlanMoveIn,
    *,
    actor_id: int | None,
) -> WorkPlanItem:
    """Swap a row with its neighbor in the list and Gantt stack. Dates stay put."""
    rows = list_items(session, row.award_id)
    index = next(
        i for i, item in enumerate(rows) if item.work_plan_item_id == row.work_plan_item_id
    )
    neighbor_index = index - 1 if payload.direction == "up" else index + 1
    if 0 <= neighbor_index < len(rows):
        neighbor = rows[neighbor_index]
        row.sort_order, neighbor.sort_order = neighbor.sort_order, row.sort_order
        session.flush()
        _renormalize(session, row.award_id)
        record_event(
            session,
            action="work_plan_move",
            entity_type="work_plan_item",
            entity_id=row.work_plan_item_id,
            actor_user_id=actor_id,
            detail={"direction": payload.direction},
        )
    return row


def delete_item(session: Session, row: WorkPlanItem, *, actor_id: int | None) -> None:
    """Delete a work-plan row."""
    item_id = row.work_plan_item_id
    session.delete(row)
    session.flush()
    record_event(
        session,
        action="work_plan_delete",
        entity_type="work_plan_item",
        entity_id=item_id,
        actor_user_id=actor_id,
    )


def _pct(part: int, whole: int) -> int:
    if whole <= 0:
        return 0
    return max(0, min(100, part * 100 // whole))


def build_gantt(
    session: Session,
    *,
    award_id: int | None,
    as_of: date | None = None,
) -> WorkGanttOut:
    """Compute presentation geometry and progress fill from work-plan rows."""
    as_of = as_of or datetime.now(UTC).date()
    query = select(WorkPlanItem).order_by(
        WorkPlanItem.award_id,
        WorkPlanItem.sort_order,
        WorkPlanItem.work_plan_item_id,
    )
    if award_id is not None:
        try:
            require_award(session, award_id)
        except ValueError as exc:
            raise WorkPlanError(str(exc)) from exc
        query = query.where(WorkPlanItem.award_id == award_id)
    rows = list(session.scalars(query))
    if not rows:
        return WorkGanttOut(as_of=as_of.isoformat(), chart_start=None, chart_end=None, bars=[])
    chart_start = min(date.fromisoformat(row.start_date) for row in rows)
    chart_end = max(date.fromisoformat(row.due_date) for row in rows)
    whole = (chart_end - chart_start).days
    awards: dict[int, Award] = {}
    bars: list[WorkGanttBarOut] = []
    for row in rows:
        award = awards.get(row.award_id)
        if award is None:
            award = session.get(Award, row.award_id)
            if award is None:
                continue
            awards[row.award_id] = award
        start = date.fromisoformat(row.start_date)
        due = max(start, date.fromisoformat(row.due_date))
        if row.percent_complete_bp >= 10000:
            lane = "completed"
        elif due < as_of:
            lane = "behind"
        else:
            lane = "remaining"
        bars.append(
            WorkGanttBarOut(
                work_plan_item_id=row.work_plan_item_id,
                award_id=row.award_id,
                award_short_code=award.short_code,
                requirement_code=row.requirement_code,
                title=row.title,
                start_date=start.isoformat(),
                due_date=due.isoformat(),
                percent_complete_bp=row.percent_complete_bp,
                lane=lane,
                offset_pct=_pct((start - chart_start).days, whole),
                width_pct=max(1, _pct((due - start).days, whole)),
                complete_width_pct=row.percent_complete_bp // 100,
            )
        )
    return WorkGanttOut(
        as_of=as_of.isoformat(),
        chart_start=chart_start.isoformat(),
        chart_end=chart_end.isoformat(),
        bars=bars,
    )
