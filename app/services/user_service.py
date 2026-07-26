"""User management business logic (API_SPEC mục 3).

Security: these endpoints are MENTOR/ADMIN only (enforced by the router's
`require_role`). Self-lock and self-delete are refused so an admin cannot lock
themselves out. Deletion is a soft delete (CLAUDE.md mục 6).
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import Role, User, UserStatus
from app.schemas.user import UserCreate, UserListItem, UserOut, UserProfileUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_query(
    *, search: str | None, role: Role | None, status_: UserStatus | None,
) -> Select:
    """Build the (filtered) list query; soft-deleted users are excluded."""
    stmt = select(User).where(User.deleted_at.is_(None))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if status_ is not None:
        stmt = stmt.where(User.status == status_)
    return stmt.order_by(User.id.desc())


def get_user(db: Session, user_id: int) -> User:
    """Fetch a non-deleted user or raise 404."""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# --------------------------------------------------------------------------- #
# Serialization (resolves mentor_id -> mentor_name/mentor_email in one query)
# --------------------------------------------------------------------------- #
def _mentor_map(db: Session, users: list[User]) -> dict[int, tuple[str, str]]:
    """mentor user_id -> (full_name, email) for the mentors of `users`."""
    ids = {u.mentor_id for u in users if u.mentor_id is not None}
    if not ids:
        return {}
    rows = db.execute(
        select(User.id, User.full_name, User.email).where(User.id.in_(ids))
    ).all()
    return {uid: (name, email) for uid, name, email in rows}


def serialize(db: Session, users: list[User], schema: type = UserOut) -> list:
    """Build UserOut/UserListItem objects with the mentor fields filled in."""
    mentors = _mentor_map(db, users)
    items = []
    for u in users:
        out = schema.model_validate(u)
        if u.mentor_id is not None:
            out.mentor_name, out.mentor_email = mentors.get(u.mentor_id, (None, None))
        items.append(out)
    return items


def serialize_one(db: Session, user: User, schema: type = UserOut):
    return serialize(db, [user], schema)[0]


def serialize_list(db: Session, users: list[User]) -> list[UserListItem]:
    return serialize(db, users, UserListItem)


def create_user(db: Session, data: UserCreate) -> User:
    """Create a MENTOR/ADMIN account. 409 if the email already exists."""
    # Conflict check includes soft-deleted rows (email has a UNIQUE index).
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered",
        )
    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=security.hash_password(data.password),
        role=data.role,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_status(db: Session, target: User, new_status: UserStatus, actor: User) -> User:
    """Lock/unlock `target`. Refuses to lock the caller's own account (400)."""
    if new_status == UserStatus.LOCKED and target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot lock your own account",
        )
    target.status = new_status
    db.commit()
    db.refresh(target)
    return target


def update_profile(db: Session, target: User, data: UserProfileUpdate) -> User:
    """Update the intern profile fields (MENTOR/ADMIN only, see router).

    Only fields present in the payload change; an explicit `null` clears one.
    400 if `mentor_id` is not an existing MENTOR/ADMIN, or if the resulting
    internship window ends before it starts.
    """
    fields = data.model_dump(exclude_unset=True)
    mentor_id = fields.get("mentor_id")
    if mentor_id is not None:
        mentor = db.get(User, mentor_id)
        if mentor is None or mentor.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="mentor_id does not exist",
            )
        if mentor.role not in (Role.MENTOR, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mentor_id must reference a MENTOR or ADMIN account",
            )
        if mentor.id == target.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user cannot be their own mentor",
            )

    start = fields.get("start_date", target.start_date)
    end = fields.get("end_date", target.end_date)
    if start is not None and end is not None and end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must not be earlier than start_date",
        )

    for key, value in fields.items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


def soft_delete(db: Session, target: User, actor: User) -> None:
    """Soft-delete `target` (set deleted_at). Refuses self-deletion (400)."""
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    if target.deleted_at is None:
        target.deleted_at = _now()
        db.commit()
