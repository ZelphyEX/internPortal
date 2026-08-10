"""Yêu cầu chuyển vai trò (Thực tập sinh <-> Mentor).

  * Người dùng : xem yêu cầu của mình, gửi yêu cầu, tự rút lại.
  * ADMIN      : xem hàng đợi, duyệt, từ chối.
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import AdminRequired, CurrentUser, DbSession
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.models.role_request import RoleRequestStatus
from app.models.user import Role
from app.schemas.common import Page
from app.schemas.role_request import RoleRequestCreate, RoleRequestOut
from app.services import role_request_service as svc

router = APIRouter(prefix="/role-requests", tags=["role-requests"])


@router.get("/me", response_model=RoleRequestOut | None)
def get_my_request(db: DbSession, current_user: CurrentUser) -> RoleRequestOut | None:
    """Yêu cầu đang chờ duyệt của chính mình, hoặc `null` nếu không có."""
    req = svc.get_pending_for_user(db, current_user.id)
    return svc.serialize(req) if req is not None else None


@router.post("", response_model=RoleRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RoleRequestCreate, db: DbSession, current_user: CurrentUser,
) -> RoleRequestOut:
    """Gửi yêu cầu chuyển vai trò.

    * `to_role=MENTOR` (đang là Thực tập sinh): tạo yêu cầu **chờ Admin duyệt**,
      `applied=false`.
    * `to_role=INTERN` (đang là Mentor): là hạ quyền nên **áp dụng ngay**,
      `applied=true` — client cần gọi lại `GET /auth/me` để cập nhật giao diện.

    400 nếu là Admin / đã ở vai trò đó, 409 nếu đang có yêu cầu chờ duyệt.
    """
    return svc.create(db, current_user, Role(payload.to_role.value))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_request(db: DbSession, current_user: CurrentUser) -> None:
    """Rút lại yêu cầu của mình khi nó **chưa** được duyệt. 404 nếu không có."""
    svc.cancel_own(db, current_user)


@router.get("", response_model=Page[RoleRequestOut])
def list_requests(
    db: DbSession,
    current_user: AdminRequired,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    status_: Annotated[
        RoleRequestStatus | None, Query(alias="status", description="mặc định: tất cả"),
    ] = None,
) -> Page[RoleRequestOut]:
    """ADMIN. Hàng đợi yêu cầu, ai gửi trước xếp trước."""
    rows, total, pages = paginate(db, svc.list_query(status_), page=page, size=size)
    return Page(
        items=[svc.serialize(r) for r in rows],
        total=total, page=page, size=size, pages=pages,
    )


@router.patch("/{request_id}/approve", response_model=RoleRequestOut)
def approve_request(
    request_id: int, db: DbSession, current_user: AdminRequired,
) -> RoleRequestOut:
    """ADMIN duyệt yêu cầu -> vai trò của người gửi được đổi ngay.

    400 nếu yêu cầu đã được xử lý trước đó, 404 nếu không tồn tại.
    """
    return svc.approve(db, svc.get_request(db, request_id), current_user)


@router.patch("/{request_id}/reject", response_model=RoleRequestOut)
def reject_request(
    request_id: int, db: DbSession, current_user: AdminRequired,
) -> RoleRequestOut:
    """ADMIN từ chối yêu cầu -> vai trò giữ nguyên. Người dùng có thể gửi lại sau."""
    return svc.reject(db, svc.get_request(db, request_id), current_user)
