"""User model + role/status enums."""
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import DEPARTMENT_ENUM, Department, pg_enum


class Role(str, enum.Enum):
    """Role hierarchy: ADMIN > MENTOR > INTERN (see app.core.deps.require_role)."""
    ADMIN = "ADMIN"
    MENTOR = "MENTOR"
    INTERN = "INTERN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    # Đăng ký làm MENTOR nhưng chưa được ADMIN duyệt: chưa đăng nhập được,
    # nằm trong hàng đợi ở tab "Mentor" của Admin (PATCH /users/{id}/approve).
    PENDING = "PENDING"


# Một type object dùng chung -> chỉ một CREATE TYPE, dù có bảng khác cũng dùng
# `user_role` (xem app/models/role_request.py).
ROLE_ENUM = pg_enum(Role, "user_role")
USER_STATUS_ENUM = pg_enum(UserStatus, "user_status")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(ROLE_ENUM, default=Role.INTERN, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        USER_STATUS_ENUM, default=UserStatus.ACTIVE, nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Soft delete: set instead of physically removing the row.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ----------------------------------------------------------------------- #
    # Intern profile (docs/backend-requirements.md mục 1).
    # All nullable: only meaningful for role=INTERN, and filled in by a
    # MENTOR/ADMIN via PATCH /users/{id}/profile.
    # ----------------------------------------------------------------------- #
    # Khối "Thông tin Hành chính & Đào tạo" (phone, university, mentor_id,
    # start_date, end_date) đã bị bỏ khỏi bảng — xem migration d5c8a2e64f19.
    department: Mapped[Department | None] = mapped_column(DEPARTMENT_ENUM, nullable=True)
    major: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Evaluation score and attendance rate (%), both 0..100.
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    attendance_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
