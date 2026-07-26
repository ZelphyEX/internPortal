"""User management router (API_SPEC mục 3). MENTOR/ADMIN only."""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import AdminRequired, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.models.user import Role, UserStatus
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserListItem, UserOut, UserProfileUpdate
from app.services import user_service as svc

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserListItem])
def list_users(
    db: DbSession,
    current_user: MentorRequired,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in name or email")] = None,
    role: Annotated[Role | None, Query()] = None,
    status_: Annotated[UserStatus | None, Query(alias="status")] = None,
) -> Page[UserListItem]:
    stmt = svc.list_query(search=search, role=role, status_=status_)
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(
        items=svc.serialize_list(db, list(rows)),
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, current_user: AdminRequired) -> UserOut:
    """ADMIN only. Create a MENTOR/ADMIN account. 409 if the email exists."""
    return svc.serialize_one(db, svc.create_user(db, payload))


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DbSession, current_user: MentorRequired) -> UserOut:
    return svc.serialize_one(db, svc.get_user(db, user_id))


@router.patch("/{user_id}/profile", response_model=UserOut)
def update_user_profile(
    user_id: int, payload: UserProfileUpdate, db: DbSession, current_user: MentorRequired,
) -> UserOut:
    """MENTOR/ADMIN. Update an intern's profile (department, mentor, dates,
    school, score...). Send only the fields you want to change; an explicit
    `null` clears one. To edit your own name/avatar use `PATCH /auth/me`."""
    target = svc.get_user(db, user_id)
    return svc.serialize_one(db, svc.update_profile(db, target, payload))


@router.patch("/{user_id}/lock", response_model=UserOut)
def lock_user(user_id: int, db: DbSession, current_user: MentorRequired) -> UserOut:
    target = svc.get_user(db, user_id)
    return svc.serialize_one(
        db, svc.set_status(db, target, UserStatus.LOCKED, actor=current_user)
    )


@router.patch("/{user_id}/unlock", response_model=UserOut)
def unlock_user(user_id: int, db: DbSession, current_user: MentorRequired) -> UserOut:
    target = svc.get_user(db, user_id)
    return svc.serialize_one(
        db, svc.set_status(db, target, UserStatus.ACTIVE, actor=current_user)
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbSession, current_user: AdminRequired) -> None:
    """ADMIN only. Soft delete (sets deleted_at)."""
    target = svc.get_user(db, user_id)
    svc.soft_delete(db, target, actor=current_user)
