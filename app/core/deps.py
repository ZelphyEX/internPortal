"""FastAPI dependencies shared by every router (Dev A, task 1.2).

Dev B: use these for auth/permission on ALL protected endpoints — never
trust the frontend. Typical usage:

    from app.core.deps import DbSession, CurrentUser, require_role
    from app.models.user import Role

    @router.get("/documents")
    def list_docs(db: DbSession, user: CurrentUser): ...          # any logged-in user

    @router.post("/documents")
    def create_doc(db: DbSession, user: MentorRequired): ...      # MENTOR or ADMIN

    @router.post("/users")
    def create_user(db: DbSession, user: AdminRequired): ...      # ADMIN only

    # or explicitly:
    @router.delete("/tags/{id}")
    def del_tag(db: DbSession, user: User = Depends(require_role(Role.MENTOR))): ...
"""
from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import Role, User, UserStatus

# Role hierarchy — ADMIN inherits MENTOR inherits INTERN.
_ROLE_LEVEL: dict[Role, int] = {
    Role.INTERN: 1,
    Role.MENTOR: 2,
    Role.ADMIN: 3,
}

# Reads the "Authorization: Bearer <token>" header. auto_error=False so we
# raise our own 401 with a WWW-Authenticate header and a consistent detail.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Paste the access_token returned by /auth/login.",
)

_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated User from the bearer access token.

    401 if the token is missing/invalid/expired or the user no longer exists
    (including soft-deleted). 403 if the account is LOCKED.
    """
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers=_UNAUTH_HEADERS,
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=_UNAUTH_HEADERS,
        )

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers=_UNAUTH_HEADERS,
        )

    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers=_UNAUTH_HEADERS,
        )
    if user.status == UserStatus.PENDING:
        # Mentor đăng ký nhưng Admin chưa duyệt -> chưa được dùng bất kỳ API nào.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PENDING_APPROVAL: Tài khoản Mentor của bạn đang chờ Quản trị viên duyệt.",
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )
    return user


def require_role(min_role: Role) -> Callable[..., User]:
    """Dependency factory: require the current user's role >= `min_role`.

    Returns a dependency that yields the current User (so the handler can use
    it directly) or raises 403 if the role is insufficient.
    """
    def checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if _ROLE_LEVEL[current_user.role] < _ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return checker


# --------------------------------------------------------------------------- #
# Ready-to-use annotated shortcuts (ergonomic for Dev B)
# --------------------------------------------------------------------------- #
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]  # any active user
MentorRequired = Annotated[User, Depends(require_role(Role.MENTOR))]  # MENTOR+ADMIN
AdminRequired = Annotated[User, Depends(require_role(Role.ADMIN))]  # ADMIN only
