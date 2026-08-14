"""Tasks router (backend-requirements mục 3).

Read: any authenticated user — an INTERN only sees tasks assigned to them.
Create/delete: MENTOR/ADMIN. Update: MENTOR/ADMIN on any task; an INTERN may
update `status` and `pr_url` on their own task only.
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.models.task import TaskPriority, TaskStatus
from app.schemas.common import Page
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services import task_service as svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=Page[TaskOut])
def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    project_id: Annotated[int | None, Query()] = None,
    assigned_intern_id: Annotated[
        int | None,
        Query(
            description=(
                "MENTOR only; an intern always gets their own tasks. Matches tasks "
                "where this person is ONE of possibly several assignees."
            )
        ),
    ] = None,
    status_: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
) -> Page[TaskOut]:
    stmt = svc.list_query(
        viewer=current_user, project_id=project_id,
        assigned_intern_id=assigned_intern_id, status_=status_, priority=priority,
    )
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(
        items=svc.to_out_list(db, list(rows)),
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: DbSession, current_user: MentorRequired) -> TaskOut:
    """MENTOR/ADMIN. `mentor_id` defaults to the caller.

    `assigned_intern_ids` nhận 0, 1, hoặc nhiều người (vd cả nhóm/dự án) — tất cả
    cùng gắn vào MỘT task này, không tách thành nhiều task riêng.
    """
    return svc.to_out(db, svc.create_task(db, payload, current_user))


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: DbSession, current_user: CurrentUser) -> TaskOut:
    """403 for an intern the task is not assigned to."""
    t = svc.get_task(db, task_id)
    svc.ensure_can_view(t, current_user)
    return svc.to_out(db, t)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, payload: TaskUpdate, db: DbSession, current_user: CurrentUser,
) -> TaskOut:
    """MENTOR/ADMIN: any field. INTERN: only `status`/`pr_url` on their own
    task (403 otherwise). Moving a task to `Done` stamps `completed_at`."""
    t = svc.get_task(db, task_id)
    return svc.to_out(db, svc.update_task(db, t, payload, current_user))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_task(db, svc.get_task(db, task_id))
