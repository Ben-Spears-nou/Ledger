"""Tasks, assignments, and weekly capacity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ledger.api.deps import get_current_user, get_db, require_admin
from ledger.models import Award, Task, UserAccount
from ledger.schemas.schedule import (
    AssignmentCreate,
    AssignmentOut,
    CapacityWeekRow,
    TaskCardOut,
    TaskCreate,
    TaskUpdate,
)
from ledger.services.schedule import (
    ScheduleError,
    capacity_for_week,
    create_assignment,
    create_task,
    list_assignments,
    list_tasks,
    serialize_assignment,
    serialize_task,
    update_task,
)

award_tasks_router = APIRouter(prefix="/awards", tags=["schedule"])
tasks_router = APIRouter(prefix="/tasks", tags=["schedule"])
assignments_router = APIRouter(prefix="/assignments", tags=["schedule"])
capacity_router = APIRouter(tags=["schedule"])


def _http(exc: ScheduleError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


def _get_award(session: Session, award_id: int) -> Award:
    award = session.get(Award, award_id)
    if award is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "award not found")
    return award


@award_tasks_router.get("/{award_id}/tasks", response_model=list[TaskCardOut])
def get_award_tasks(
    award_id: int,
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> list[TaskCardOut]:
    """Slim tasks for one award (D22). Employees and admins get the same DTO."""
    _get_award(session, award_id)
    return [serialize_task(task) for task in list_tasks(session, award_id)]


@award_tasks_router.post(
    "/{award_id}/tasks",
    response_model=TaskCardOut,
    status_code=status.HTTP_201_CREATED,
)
def post_award_task(
    award_id: int,
    payload: TaskCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> TaskCardOut:
    """Create a task on an award (admin)."""
    award = _get_award(session, award_id)
    try:
        task = create_task(session, award, payload, actor_id=admin.user_account_id)
    except ScheduleError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_task(task)


@award_tasks_router.patch("/{award_id}/tasks/{task_id}", response_model=TaskCardOut)
def patch_award_task(
    award_id: int,
    task_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> TaskCardOut:
    """Close or rename a task (admin)."""
    _get_award(session, award_id)
    task = session.get(Task, task_id)
    if task is None or task.award_id != award_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    try:
        task = update_task(session, task, payload)
    except ScheduleError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_task(task)


@tasks_router.get("", response_model=list[TaskCardOut])
def get_tasks(
    award_id: int | None = None,
    session: Session = Depends(get_db),
    _user: UserAccount = Depends(get_current_user),
) -> list[TaskCardOut]:
    """All tasks, or one award's tasks. Slim DTO only."""
    if award_id is not None:
        _get_award(session, award_id)
    return [serialize_task(task) for task in list_tasks(session, award_id)]


@assignments_router.get("", response_model=list[AssignmentOut])
def get_assignments(
    person_id: int | None = None,
    award_id: int | None = None,
    session: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
) -> list[AssignmentOut]:
    """Admin: all (filterable). Employee: own rows only."""
    if user.role_code != "admin":
        if person_id is not None and person_id != user.person_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not your assignments")
        person_id = user.person_id
    return [
        serialize_assignment(row)
        for row in list_assignments(session, person_id=person_id, award_id=award_id)
    ]


@assignments_router.post(
    "",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def post_assignment(
    payload: AssignmentCreate,
    session: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
) -> AssignmentOut:
    """Create a dated assignment (admin)."""
    try:
        row = create_assignment(session, payload, actor_id=admin.user_account_id)
    except ScheduleError as exc:
        raise _http(exc) from exc
    session.flush()
    return serialize_assignment(row)


@capacity_router.get("/capacity", response_model=list[CapacityWeekRow])
def get_capacity_week(
    week_start: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _admin: UserAccount = Depends(require_admin),
) -> list[CapacityWeekRow]:
    """Planned vs capacity hours for a week (admin, informational)."""
    from datetime import UTC, datetime

    start = week_start or datetime.now(UTC).date().isoformat()
    return capacity_for_week(session, start)
