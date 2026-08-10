"""Schemas cho yêu cầu chuyển vai trò (Thực tập sinh <-> Mentor)."""
import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.role_request import RoleRequestStatus
from app.models.user import Role


class SwitchableRole(str, enum.Enum):
    """Vai trò được phép yêu cầu chuyển sang. KHÔNG có ADMIN."""
    INTERN = "INTERN"
    MENTOR = "MENTOR"


class RoleRequestCreate(BaseModel):
    to_role: SwitchableRole


class RoleRequestOut(BaseModel):
    """Một yêu cầu chuyển vai trò.

    `applied=True` nghĩa là vai trò đã đổi ngay (trường hợp Mentor tự hạ xuống
    Thực tập sinh) — frontend cần tải lại phiên để giao diện khớp vai trò mới.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    from_role: Role
    to_role: Role
    status: RoleRequestStatus
    created_at: datetime
    decided_at: datetime | None = None
    applied: bool = False
