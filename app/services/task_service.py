"""Task business logic (backend-requirements mục 3).

Visibility (CLAUDE.md mục 6): a MENTOR/ADMIN sees every task, an INTERN only
sees tasks assigned to them. An INTERN may move their own task on the board
(`status`) and submit a `pr_url`; everything else — including
`mentor_feedback` and `assigned_intern_ids` — is MENTOR/ADMIN only.
`completed_at` is maintained by the backend from `status`.

Một task giao được cho NHIỀU người cùng lúc (`Task.assignees`, N-N) — vẫn là
MỘT bản ghi Task duy nhất, không tách thành nhiều task riêng. Ai trong số
người nhận sửa (status, PR url...) là sửa chung, mọi người còn lại cùng thấy
thay đổi ngay lập tức.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task, TaskAssignee, TaskPriority, TaskStatus
from app.models.user import Role, User
from app.schemas.task import TaskAssigneeOut, TaskCreate, TaskOut, TaskUpdate

# The only fields an intern may change on their own task.
INTERN_EDITABLE_FIELDS = frozenset({"status", "pr_url"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Queries / serialization
# --------------------------------------------------------------------------- #
def list_query(
    *,
    viewer: User,
    project_id: int | None,
    assigned_intern_id: int | None,
    status_: TaskStatus | None,
    priority: TaskPriority | None,
) -> Select:
    stmt = select(Task)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if status_ is not None:
        stmt = stmt.where(Task.status == status_)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if viewer.role == Role.INTERN:
        # Ignore any requested assignee: an intern only ever sees tasks they're in.
        stmt = stmt.where(
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == viewer.id))
        )
    elif assigned_intern_id is not None:
        stmt = stmt.where(
            Task.id.in_(
                select(TaskAssignee.task_id).where(TaskAssignee.user_id == assigned_intern_id)
            )
        )
    return stmt.order_by(Task.id.desc())


def to_out_list(db: Session, tasks: list[Task]) -> list[TaskOut]:
    """Serialize with project/user labels resolved in batch queries."""
    if not tasks:
        return []
    project_ids = {t.project_id for t in tasks if t.project_id is not None}
    task_ids = [t.id for t in tasks]

    assignee_rows = db.execute(
        select(TaskAssignee.task_id, User.id, User.full_name)
        .join(User, User.id == TaskAssignee.user_id)
        .where(TaskAssignee.task_id.in_(task_ids))
        .order_by(TaskAssignee.assigned_at, TaskAssignee.id)
    ).all()
    assignees_by_task: dict[int, list[TaskAssigneeOut]] = {}
    for task_id, uid, full_name in assignee_rows:
        assignees_by_task.setdefault(task_id, []).append(
            TaskAssigneeOut(user_id=uid, full_name=full_name)
        )

    user_ids = {t.mentor_id for t in tasks if t.mentor_id is not None}
    names: dict[int, str] = {}
    if user_ids:
        names = dict(
            db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
        )

    projects: dict[int, tuple[str, str]] = {}
    if project_ids:
        projects = {
            pid: (code, title)
            for pid, code, title in db.execute(
                select(Project.id, Project.code, Project.title).where(
                    Project.id.in_(project_ids)
                )
            ).all()
        }

    items = []
    for t in tasks:
        code, title = projects.get(t.project_id, (None, None))
        items.append(
            TaskOut(
                id=t.id,
                title=t.title,
                project_id=t.project_id,
                project_code=code,
                project_title=title,
                assignees=assignees_by_task.get(t.id, []),
                mentor_id=t.mentor_id,
                mentor_name=names.get(t.mentor_id),
                status=t.status,
                priority=t.priority,
                due_date=t.due_date,
                description=t.description,
                pr_url=t.pr_url,
                mentor_feedback=t.mentor_feedback,
                completed_at=t.completed_at,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return items


def to_out(db: Session, t: Task) -> TaskOut:
    return to_out_list(db, [t])[0]


# --------------------------------------------------------------------------- #
# Access helpers
# --------------------------------------------------------------------------- #
def get_task(db: Session, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")
    return t


def _is_assignee(t: Task, user_id: int) -> bool:
    return any(a.user_id == user_id for a in t.assignees)


def ensure_can_view(t: Task, viewer: User) -> None:
    if viewer.role == Role.INTERN and not _is_assignee(t, viewer.id):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This task is not assigned to you",
        )


def _validate_project_ref(db: Session, project_id: int | None) -> None:
    if project_id is None:
        return
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="project_id does not exist",
        )


def _validate_user_ref(db: Session, field: str, user_id: int | None) -> None:
    if user_id is None:
        return
    u = db.get(User, user_id)
    if u is None or u.deleted_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field} does not exist",
        )


def _sync_completed_at(t: Task) -> None:
    """DONE -> stamp completed_at; anything else -> clear it."""
    if t.status == TaskStatus.DONE:
        if t.completed_at is None:
            t.completed_at = _now()
    else:
        t.completed_at = None


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def create_task(db: Session, data: TaskCreate, actor: User) -> Task:
    # Khử trùng: gửi lặp 1 id trong assigned_intern_ids không tạo 2 dòng liên
    # kết cho cùng 1 người (UNIQUE(task_id, user_id) sẽ chặn, nhưng khử trùng
    # trước cho gọn thay vì để lỗi DB).
    assignee_ids = list(dict.fromkeys(data.assigned_intern_ids))
    _validate_project_ref(db, data.project_id)
    _validate_user_ref(db, "mentor_id", data.mentor_id)
    for uid in assignee_ids:
        _validate_user_ref(db, "assigned_intern_ids", uid)

    t = Task(
        title=data.title,
        project_id=data.project_id,
        # Default the owning mentor to whoever created the task.
        mentor_id=data.mentor_id if data.mentor_id is not None else actor.id,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        description=data.description,
        pr_url=data.pr_url,
        assignees=[TaskAssignee(user_id=uid) for uid in assignee_ids],
    )
    _sync_completed_at(t)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# Columns that are NOT NULL: an explicit `null` means "leave unchanged".
_NOT_NULL_FIELDS = ("title", "status", "priority")


def update_task(db: Session, t: Task, data: TaskUpdate, actor: User) -> Task:
    fields = data.model_dump(exclude_unset=True)
    for key in _NOT_NULL_FIELDS:
        if key in fields and fields[key] is None:
            fields.pop(key)

    # `assigned_intern_ids` không phải cột thường trên Task (là quan hệ N-N) nên
    # tách riêng khỏi vòng `setattr` chung bên dưới.
    assignees_provided = "assigned_intern_ids" in fields
    new_assignee_ids = fields.pop("assigned_intern_ids", None)

    if actor.role == Role.INTERN:
        if not _is_assignee(t, actor.id):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="This task is not assigned to you",
            )
        forbidden = sorted(set(fields) - INTERN_EDITABLE_FIELDS)
        if assignees_provided:
            forbidden = sorted([*forbidden, "assigned_intern_ids"])
        if forbidden:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail=(
                    "An intern may only update "
                    f"{sorted(INTERN_EDITABLE_FIELDS)} on their own task "
                    f"(rejected: {forbidden})"
                ),
            )

    _validate_project_ref(db, fields.get("project_id"))
    _validate_user_ref(db, "mentor_id", fields.get("mentor_id"))
    deduped_assignee_ids: list[int] | None = None
    if new_assignee_ids is not None:
        deduped_assignee_ids = list(dict.fromkeys(new_assignee_ids))
        for uid in deduped_assignee_ids:
            _validate_user_ref(db, "assigned_intern_ids", uid)

    for key, value in fields.items():
        setattr(t, key, value)
    if deduped_assignee_ids is not None:
        # Thay TOÀN BỘ danh sách người nhận — SQLAlchemy tự xoá dòng cũ (cascade
        # delete-orphan) và thêm dòng mới khi commit.
        t.assignees = [TaskAssignee(user_id=uid) for uid in deduped_assignee_ids]
    _sync_completed_at(t)
    db.commit()
    db.refresh(t)
    return t


def delete_task(db: Session, t: Task) -> None:
    db.delete(t)
    db.commit()
