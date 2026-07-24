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
from app.schemas.user import UserCreate


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
