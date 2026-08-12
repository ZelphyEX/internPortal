"""Nghiệp vụ yêu cầu chuyển vai trò (Thực tập sinh <-> Mentor).

Luật:
  * INTERN -> MENTOR : tạo yêu cầu PENDING, chờ ADMIN duyệt. Người gửi có thể tự
    rút lại khi còn PENDING.
  * MENTOR -> INTERN : là hạ quyền nên áp dụng NGAY, không cần duyệt (frontend
    vẫn hiện popup cảnh báo trước khi gọi).
  * ADMIN : không dùng cơ chế này — vai trò Admin do hệ thống cấp.

IMPORTANT: chỉ ADMIN được duyệt/từ chối (router dùng `AdminRequired`). Không bao
giờ tin `to_role` client gửi lên để nâng quyền — nâng quyền chỉ xảy ra ở `approve`.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.role_request import RoleChangeRequest, RoleRequestStatus
from app.models.user import Role, User
from app.schemas.role_request import RoleRequestOut


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def serialize(req: RoleChangeRequest, *, applied: bool = False) -> RoleRequestOut:
    out = RoleRequestOut.model_validate(req)
    if req.user is not None:
        out.user_name = req.user.full_name
        out.user_email = req.user.email
    out.applied = applied
    return out


def list_query(status_: RoleRequestStatus | None = None) -> Select:
    """Hàng đợi cho Admin. Ai gửi trước đứng trước — duyệt xong yêu cầu đó rời
    hàng đợi nên người kế tiếp tự động lên đầu."""
    stmt = select(RoleChangeRequest)
    if status_ is not None:
        stmt = stmt.where(RoleChangeRequest.status == status_)
    return stmt.order_by(RoleChangeRequest.id.asc())


def get_pending_for_user(db: Session, user_id: int) -> RoleChangeRequest | None:
    return db.scalar(
        select(RoleChangeRequest).where(
            RoleChangeRequest.user_id == user_id,
            RoleChangeRequest.status == RoleRequestStatus.PENDING,
        )
    )


def get_request(db: Session, request_id: int) -> RoleChangeRequest:
    req = db.get(RoleChangeRequest, request_id)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy yêu cầu.",
        )
    return req


# --------------------------------------------------------------------------- #
# Người dùng tự gửi / tự rút
# --------------------------------------------------------------------------- #
def create(db: Session, actor: User, to_role: Role) -> RoleRequestOut:
    """Gửi yêu cầu chuyển vai trò. Hạ quyền (MENTOR->INTERN) áp dụng ngay."""
    if actor.role == Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản Quản trị viên không dùng chức năng chuyển vai trò.",
        )
    if to_role == actor.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bạn đang là {actor.role.value} rồi.",
        )
    if to_role not in (Role.INTERN, Role.MENTOR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chuyển được giữa Thực tập sinh và Mentor.",
        )

    existing = get_pending_for_user(db, actor.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bạn đã có một yêu cầu chuyển sang {existing.to_role.value} đang chờ "
                "duyệt. Hãy rút yêu cầu đó trước khi gửi yêu cầu mới."
            ),
        )

    req = RoleChangeRequest(
        user_id=actor.id, from_role=actor.role, to_role=to_role,
        status=RoleRequestStatus.PENDING,
    )

    # Hạ quyền thì tự áp dụng ngay: người dùng luôn được phép bỏ quyền của mình.
    applied = to_role == Role.INTERN
    if applied:
        actor.role = Role.INTERN
        req.status = RoleRequestStatus.APPROVED
        req.decided_by = actor.id
        req.decided_at = _now()

    db.add(req)
    try:
        db.commit()
    except IntegrityError:
        # Trùng unique index "một yêu cầu PENDING mỗi người" (hai tab bấm cùng lúc).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã có một yêu cầu đang chờ duyệt.",
        )
    db.refresh(req)
    return serialize(req, applied=applied)


def cancel_own(db: Session, actor: User) -> None:
    """Người dùng tự rút yêu cầu khi nó còn đang chờ duyệt."""
    req = get_pending_for_user(db, actor.id)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bạn không có yêu cầu nào đang chờ duyệt.",
        )
    req.status = RoleRequestStatus.CANCELLED
    req.decided_at = _now()
    db.commit()


# --------------------------------------------------------------------------- #
# Admin duyệt / từ chối
# --------------------------------------------------------------------------- #
def _assert_pending(req: RoleChangeRequest) -> None:
    if req.status != RoleRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yêu cầu này đã được xử lý (trạng thái {req.status.value}).",
        )


def approve(db: Session, req: RoleChangeRequest, admin: User) -> RoleRequestOut:
    """ADMIN duyệt: đổi vai trò thật của người dùng."""
    _assert_pending(req)
    target = db.get(User, req.user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người gửi yêu cầu không còn tồn tại.",
        )
    target.role = req.to_role
    req.status = RoleRequestStatus.APPROVED
    req.decided_by = admin.id
    req.decided_at = _now()
    db.commit()
    db.refresh(req)
    return serialize(req, applied=True)


def reject(db: Session, req: RoleChangeRequest, admin: User) -> RoleRequestOut:
    """ADMIN từ chối: vai trò giữ nguyên."""
    _assert_pending(req)
    req.status = RoleRequestStatus.REJECTED
    req.decided_by = admin.id
    req.decided_at = _now()
    db.commit()
    db.refresh(req)
    return serialize(req)


def settle_pending_for_user(
    db: Session, user_id: int, new_role: Role, admin: User,
) -> None:
    """Đóng yêu cầu đang chờ của một người khi ADMIN vừa TỰ TAY đổi vai trò họ.

    Không có bước này thì yêu cầu cũ vẫn nằm trong hàng đợi sau khi vai trò đã đổi
    xong — Admin thấy một yêu cầu "xin lên Mentor" của người đã là Mentor, bấm duyệt
    thì không có tác dụng gì, và badge ở thanh bên đếm sai.

    Xin đúng thứ vừa được cấp thì coi như ĐƯỢC DUYỆT; còn lại thì HUỶ (yêu cầu không
    còn ý nghĩa). Cả hai đều không đổi vai trò lần nữa — người gọi đã đổi rồi.

    KHÔNG commit: hàm này chạy chung transaction với `user_service.set_role`, để vai
    trò và hàng đợi luôn khớp nhau kể cả khi có lỗi ở giữa.
    """
    req = get_pending_for_user(db, user_id)
    if req is None:
        return
    req.status = (
        RoleRequestStatus.APPROVED
        if req.to_role == new_role
        else RoleRequestStatus.CANCELLED
    )
    req.decided_by = admin.id
    req.decided_at = _now()
