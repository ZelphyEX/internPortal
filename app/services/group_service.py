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
from app.schemas.group import GroupCreate, GroupOut, GroupUpdate

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
def add_members(db: Session, group_id: int, user_ids: list[int]) -> list[User]:
    """Add many interns at once. Skips unknown/deleted users and anyone already
    in this group. Returns the group's current member list."""
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
    if to_add:
        db.add_all(GroupMember(group_id=group_id, user_id=uid) for uid in to_add)
        db.commit()
    return list_members(db, group_id)


def remove_member(db: Session, group_id: int, user_id: int) -> None:
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
    db.delete(gm)
    db.commit()
