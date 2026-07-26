"""Auth business logic (register / login / refresh / logout / password).

Routers stay thin — they call these functions. Security rules:
  * passwords are bcrypt-hashed (never stored raw)
  * refresh tokens are stored as SHA-256 hashes in `refresh_tokens`
  * changing the password revokes all of the user's refresh tokens
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.models.auth import RefreshToken
from app.models.user import Role, User, UserStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_active_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )


def register(db: Session, *, full_name: str, email: str, password: str) -> User:
    # Conflict check includes soft-deleted rows (email has a UNIQUE index).
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered",
        )
    user = User(
        full_name=full_name,
        email=email,
        password_hash=security.hash_password(password),
        role=Role.INTERN,          # register only ever creates INTERN
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = _get_active_user_by_email(db, email)
    # Same 401 for unknown email and wrong password (no user enumeration).
    if user is None or not security.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked",
        )
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    """Return (access_token, raw_refresh_token). Stores only the refresh hash."""
    access = security.create_access_token(subject=user.id, role=user.role.value)
    raw_refresh = security.create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=security.hash_refresh_token(raw_refresh),
        expires_at=security.refresh_token_expires_at(),
    ))
    db.commit()
    return access, raw_refresh


def refresh_access_token(db: Session, raw_refresh: str) -> str:
    token_hash = security.hash_refresh_token(raw_refresh)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if rt is None or rt.revoked_at is not None or rt.expires_at <= _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = db.get(User, rt.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token",
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked",
        )
    return security.create_access_token(subject=user.id, role=user.role.value)


def logout(db: Session, user: User, raw_refresh: str) -> None:
    """Revoke the given refresh token if it belongs to `user`. Idempotent."""
    token_hash = security.hash_refresh_token(raw_refresh)
    rt = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user.id,
        )
    )
    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = _now()
        db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not security.verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect",
        )
    user.password_hash = security.hash_password(new_password)
    # Invalidate existing sessions after a password change.
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()


def update_me(db: Session, user: User, fields: dict) -> User:
    for key, value in fields.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
