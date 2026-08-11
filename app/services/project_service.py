"""Project business logic (backend-requirements mục 2).

Visibility (CLAUDE.md mục 6 — an intern must not see other people's data):
a MENTOR/ADMIN sees every project, an INTERN only sees projects they lead or
are a member of. Writes are MENTOR/ADMIN only (enforced by the router).
Deletion is a soft delete because tasks keep referencing the project.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import Department
from app.models.project import Project, ProjectMember, ProjectStatus
from app.models.user import Role, User
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailOut,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services.tag_service import resolve_tags


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _member_project_ids(user_id: int):
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)


def _only_visible_to(stmt: Select, user_id: int) -> Select:
    return stmt.where(
        or_(Project.lead_user_id == user_id, Project.id.in_(_member_project_ids(user_id)))
    )


# --------------------------------------------------------------------------- #
# Queries / serialization
# --------------------------------------------------------------------------- #
def list_query(
    *,
    viewer: User,
    search: str | None,
    department: Department | None,
    status_: ProjectStatus | None,
    member_id: int | None,
) -> Select:
    stmt = select(Project).where(Project.deleted_at.is_(None))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Project.title.ilike(like), Project.code.ilike(like)))
    if department is not None:
        stmt = stmt.where(Project.department == department)
    if status_ is not None:
        stmt = stmt.where(Project.status == status_)
    if member_id is not None:
        stmt = stmt.where(Project.id.in_(_member_project_ids(member_id)))
    if viewer.role == Role.INTERN:
        stmt = _only_visible_to(stmt, viewer.id)
    return stmt.order_by(Project.id.desc())


def member_counts(db: Session, project_ids: list[int]) -> dict[int, int]:
    """project_id -> number of (non-deleted) members."""
    if not project_ids:
        return {}
    rows = db.execute(
        select(ProjectMember.project_id, func.count(ProjectMember.id))
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id.in_(project_ids), User.deleted_at.is_(None))
        .group_by(ProjectMember.project_id)
    ).all()
    return {pid: cnt for pid, cnt in rows}


def lead_names(db: Session, projects: list[Project]) -> dict[int, str]:
    ids = {p.lead_user_id for p in projects if p.lead_user_id is not None}
    if not ids:
        return {}
    return dict(
        db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()
    )


def list_members(db: Session, project_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id, User.deleted_at.is_(None))
            .order_by(User.full_name, User.id)
        ).all()
    )


def to_out(p: Project, *, member_count: int, lead_name: str | None) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        code=p.code,
        title=p.title,
        department=p.department,
        status=p.status,
        lead_user_id=p.lead_user_id,
        lead_name=lead_name,
        progress_percent=p.progress_percent,
        deadline=p.deadline,
        description=p.description,
        tags=[t.name for t in p.tags],
        member_count=member_count,
        created_at=p.created_at,
    )


def to_out_one(db: Session, p: Project) -> ProjectOut:
    counts = member_counts(db, [p.id])
    return to_out(
        p,
        member_count=counts.get(p.id, 0),
        lead_name=lead_names(db, [p]).get(p.lead_user_id),
    )


def to_detail(db: Session, p: Project) -> ProjectDetailOut:
    members = list_members(db, p.id)
    base = to_out(
        p,
        member_count=len(members),
        lead_name=lead_names(db, [p]).get(p.lead_user_id),
    )
    return ProjectDetailOut(
        **base.model_dump(),
        members=[ProjectMemberOut.model_validate(m) for m in members],
    )


# --------------------------------------------------------------------------- #
# Access helpers
# --------------------------------------------------------------------------- #
def get_project(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return p


def is_member(db: Session, project_id: int, user_id: int) -> bool:
    return db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    ) is not None


def ensure_can_view(db: Session, p: Project, viewer: User) -> None:
    """An intern may only see a project they lead or belong to (else 403)."""
    if viewer.role != Role.INTERN:
        return
    if p.lead_user_id == viewer.id or is_member(db, p.id, viewer.id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not a member of this project",
    )


def _ensure_code_free(db: Session, code: str, exclude_id: int | None = None) -> None:
    stmt = select(Project.id).where(Project.code == code)
    if exclude_id is not None:
        stmt = stmt.where(Project.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Project code already exists",
        )


def _validate_lead(db: Session, lead_user_id: int | None) -> None:
    if lead_user_id is None:
        return
    lead = db.get(User, lead_user_id)
    if lead is None or lead.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="lead_user_id does not exist",
        )


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def create_project(db: Session, data: ProjectCreate) -> Project:
    """One transaction: project + tag links + initial members."""
    _ensure_code_free(db, data.code)
    _validate_lead(db, data.lead_user_id)
    p = Project(
        code=data.code,
        title=data.title,
        department=data.department,
        status=data.status,
        lead_user_id=data.lead_user_id,
        progress_percent=data.progress_percent,
        deadline=data.deadline,
        description=data.description,
    )
    p.tags = resolve_tags(db, data.tag_ids)
    db.add(p)
    db.flush()  # need p.id for the member rows
    for uid in _eligible_user_ids(db, data.member_ids):
        db.add(ProjectMember(project_id=p.id, user_id=uid))
    db.commit()
    db.refresh(p)
    return p


# Columns that are NOT NULL: an explicit `null` means "leave unchanged"
# rather than a 500 from the database.
_NOT_NULL_FIELDS = ("code", "title", "status", "progress_percent")


def update_project(db: Session, p: Project, data: ProjectUpdate) -> Project:
    fields = data.model_dump(exclude_unset=True)
    for key in _NOT_NULL_FIELDS:
        if key in fields and fields[key] is None:
            fields.pop(key)
    if "code" in fields:
        _ensure_code_free(db, fields["code"], exclude_id=p.id)
    if "lead_user_id" in fields:
        _validate_lead(db, fields["lead_user_id"])
    if "tag_ids" in fields:  # present (even []) -> replace tag links
        p.tags = resolve_tags(db, fields.pop("tag_ids") or [])
    for key, value in fields.items():
        setattr(p, key, value)
    db.commit()
    db.refresh(p)
    return p


def soft_delete(db: Session, p: Project) -> None:
    """Soft delete (sets deleted_at) — tasks keep pointing at the project."""
    if p.deleted_at is None:
        p.deleted_at = _now()
        db.commit()


# --------------------------------------------------------------------------- #
# Membership
# --------------------------------------------------------------------------- #
def _eligible_user_ids(db: Session, user_ids: list[int]) -> set[int]:
    """Subset of `user_ids` that are existing, non-deleted users."""
    wanted = set(user_ids)
    if not wanted:
        return set()
    return set(
        db.scalars(
            select(User.id).where(User.id.in_(wanted), User.deleted_at.is_(None))
        ).all()
    )


def add_members(db: Session, project_id: int, user_ids: list[int]) -> list[User]:
    """Bulk add in one transaction. Skips unknown/deleted users and anyone
    already in the project. Returns the current member list."""
    get_project(db, project_id)  # 404 if missing
    valid = _eligible_user_ids(db, user_ids)
    already = set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id.in_(valid),
            )
        ).all()
    )
    to_add = valid - already
    if to_add:
        db.add_all(ProjectMember(project_id=project_id, user_id=uid) for uid in to_add)
        db.commit()
    return list_members(db, project_id)


# --------------------------------------------------------------------------- #
# Gán theo nhóm — đối xứng với assignment_service (xem giải thích ở đó)
# --------------------------------------------------------------------------- #
def project_ids_for_group(db: Session, group_id: int) -> set[int]:
    """Các dự án mà nhóm này đang được gán vào."""
    return set(
        db.scalars(
            select(ProjectMember.project_id)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                ProjectMember.source_group_id == group_id,
                Project.deleted_at.is_(None),
            )
            .distinct()
        ).all()
    )


def add_group(db: Session, project_id: int, group_id: int) -> tuple[int, int]:
    """Gán cả một NHÓM vào dự án. Trả về (thêm mới, bỏ qua vì đã là thành viên).

    Ghi `source_group_id` để người vào nhóm sau cũng tự được thêm vào dự án này.
    Người đã là thành viên từ trước giữ nguyên nguồn cũ — nếu ghi đè thành "vào
    bằng nhóm" thì lúc họ rời nhóm sẽ bị gỡ oan khỏi dự án.
    """
    from app.models.group import Group, GroupMember

    get_project(db, project_id)  # 404 nếu dự án không tồn tại
    if db.get(Group, group_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member_ids = set(
        db.scalars(
            select(GroupMember.user_id)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id, User.deleted_at.is_(None))
        ).all()
    )
    if not member_ids:
        return 0, 0
    already = set(
        db.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id.in_(member_ids),
            )
        ).all()
    )
    to_add = member_ids - already
    if to_add:
        db.add_all(
            ProjectMember(project_id=project_id, user_id=uid, source_group_id=group_id)
            for uid in to_add
        )
        db.commit()
    return len(to_add), len(already)


def sync_new_group_members(db: Session, group_id: int, user_ids: set[int]) -> int:
    """Thêm người vừa vào nhóm vào mọi dự án mà nhóm đang tham gia.

    Không commit — người gọi commit chung một transaction.
    """
    if not user_ids:
        return 0
    project_ids = project_ids_for_group(db, group_id)
    if not project_ids:
        return 0
    existing = {
        (pid, uid)
        for pid, uid in db.execute(
            select(ProjectMember.project_id, ProjectMember.user_id).where(
                ProjectMember.project_id.in_(project_ids),
                ProjectMember.user_id.in_(user_ids),
            )
        ).all()
    }
    created = [
        ProjectMember(project_id=pid, user_id=uid, source_group_id=group_id)
        for pid in project_ids
        for uid in user_ids
        if (pid, uid) not in existing
    ]
    if created:
        db.add_all(created)
    return len(created)


def revoke_for_leaving_member(db: Session, group_id: int, user_id: int) -> tuple[int, int]:
    """Xử lý thành viên dự án khi một người rời nhóm. Trả về (đã gỡ, giữ lại).

    Chỉ đụng tới tư cách thành viên ĐẾN TỪ nhóm này. Nếu người đó đang có task
    trong dự án thì KHÔNG gỡ (task sẽ thành mồ côi) — chuyển thành thành viên
    thêm lẻ (`source_group_id = NULL`).
    """
    from app.models.task import Task

    from_group = list(
        db.scalars(
            select(ProjectMember).where(
                ProjectMember.source_group_id == group_id,
                ProjectMember.user_id == user_id,
            )
        ).all()
    )
    if not from_group:
        return 0, 0

    has_tasks = set(
        db.scalars(
            select(Task.project_id).where(
                Task.project_id.in_([m.project_id for m in from_group]),
                Task.assigned_intern_id == user_id,
            )
        ).all()
    )
    removed = kept = 0
    for m in from_group:
        if m.project_id in has_tasks:
            m.source_group_id = None
            kept += 1
        else:
            db.delete(m)
            removed += 1
    return removed, kept


def remove_member(db: Session, project_id: int, user_id: int) -> None:
    get_project(db, project_id)  # 404 if missing
    pm = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if pm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this project",
        )
    db.delete(pm)
    db.commit()
