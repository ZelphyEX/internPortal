"""Group / membership business logic (API_SPEC mục 4).

Bulk add-members runs in a single transaction and skips duplicates (same
group) and unknown/soft-deleted users instead of erroring (CLAUDE.md mục 6).
"""
from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import (
    AddMembersResult,
    GroupCreate,
    GroupOut,
    GroupUpdate,
    RemoveMemberResult,
)

_IN_USE = "Group is referenced by roadmap assignments"


# ---------- queries / helpers ----------
def list_query(*, search: str | None, cohort: str | None) -> Select:
    stmt = select(Group)
    if search:
        stmt = stmt.where(Group.name.ilike(f"%{search}%"))
    if cohort:
        stmt = stmt.where(Group.cohort == cohort)
    return stmt.order_by(Group.id.desc())


def member_counts(db: Session, group_ids: list[int]) -> dict[int, int]:
    """group_id -> number of (non-deleted) members."""
    if not group_ids:
        return {}
    rows = db.execute(
        select(GroupMember.group_id, func.count(GroupMember.id))
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id.in_(group_ids), User.deleted_at.is_(None))
        .group_by(GroupMember.group_id)
    ).all()
    return {gid: cnt for gid, cnt in rows}


def to_group_out(g: Group, count: int) -> GroupOut:
    return GroupOut(
        id=g.id, name=g.name, cohort=g.cohort, description=g.description,
        member_count=count,
    )


def get_group(db: Session, group_id: int) -> Group:
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return g


def list_members(db: Session, group_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id, User.deleted_at.is_(None))
            .order_by(User.full_name, User.id)
        ).all()
    )


# ---------- CRUD ----------
def create_group(db: Session, data: GroupCreate) -> Group:
    g = Group(name=data.name, cohort=data.cohort, description=data.description)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def update_group(db: Session, g: Group, data: GroupUpdate) -> Group:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(g, key, value)
    db.commit()
    db.refresh(g)
    return g


def delete_group(db: Session, g: Group) -> None:
    """Delete the group and its memberships (one transaction). 409 if any
    roadmap assignment still references it via source_group_id."""
    try:
        db.query(GroupMember).filter(GroupMember.group_id == g.id).delete(
            synchronize_session=False
        )
        db.delete(g)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_IN_USE)


# ---------- membership ----------
def add_members(db: Session, group_id: int, user_ids: list[int]) -> AddMembersResult:
    """Thêm nhiều người vào nhóm. Bỏ qua user không tồn tại/đã xoá và người đã ở
    trong nhóm.

    QUAN TRỌNG — người mới **kế thừa ngay** mọi lộ trình và dự án đang gán cho nhóm.
    Trước đây không có bước này: gán lộ trình cho nhóm chỉ chép cho những ai CÓ MẶT
    lúc bấm gán, nên ai vào nhóm sau sẽ không thấy lộ trình nào cả.

    Cả việc thêm thành viên lẫn kế thừa nằm trong MỘT transaction: hoặc vào nhóm và
    nhận đủ lộ trình/dự án, hoặc không có gì (không để trạng thái nửa vời).
    """
    get_group(db, group_id)  # 404 if group missing
    wanted = set(user_ids)
    # Only existing, non-deleted users are eligible.
    valid = set(
        db.scalars(
            select(User.id).where(User.id.in_(wanted), User.deleted_at.is_(None))
        ).all()
    )
    already = set(
        db.scalars(
            select(GroupMember.user_id).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id.in_(valid),
            )
        ).all()
    )
    to_add = valid - already
    roadmaps = projects = 0
    if to_add:
        db.add_all(GroupMember(group_id=group_id, user_id=uid) for uid in to_add)
        # Import tại chỗ: assignment_service/project_service không import ngược lại
        # group_service, nhưng để ở đây cho rõ đây là hiệu ứng phụ của việc vào nhóm.
        from app.services import assignment_service, project_service

        roadmaps = assignment_service.sync_new_group_members(db, group_id, to_add)
        projects = project_service.sync_new_group_members(db, group_id, to_add)
        db.commit()
    return AddMembersResult(
        members=list_members(db, group_id),
        added_count=len(to_add),
        skipped_existing=len(already),
        inherited_roadmaps=roadmaps,
        inherited_projects=projects,
    )


def remove_member(db: Session, group_id: int, user_id: int) -> RemoveMemberResult:
    """Gỡ một người khỏi nhóm.

    Chỉ thu hồi những lộ trình/dự án người đó có **vì thuộc nhóm này**, và chỉ khi
    họ chưa động vào (chưa hoàn thành bài học nào / chưa được giao task nào). Phần
    đã có tiến độ được giữ lại và chuyển thành gán cá nhân — rời nhóm không được
    phép xoá công sức đã bỏ ra. Gán lẻ từ đầu thì không đụng tới.
    """
    get_group(db, group_id)  # 404 if group missing
    gm = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )
    if gm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this group"
        )
    from app.services import assignment_service, project_service

    roadmaps_removed, roadmaps_kept = assignment_service.revoke_for_leaving_member(
        db, group_id, user_id
    )
    projects_removed, projects_kept = project_service.revoke_for_leaving_member(
        db, group_id, user_id
    )
    db.delete(gm)
    db.commit()
    return RemoveMemberResult(
        revoked_roadmaps=roadmaps_removed,
        kept_roadmaps=roadmaps_kept,
        revoked_projects=projects_removed,
        kept_projects=projects_kept,
    )
