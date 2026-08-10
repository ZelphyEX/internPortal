"""Yêu cầu chuyển vai trò (Thực tập sinh <-> Mentor).

Luật nghiệp vụ (xem `app.services.role_request_service`):
  * INTERN -> MENTOR : tạo yêu cầu ở trạng thái PENDING, phải chờ ADMIN duyệt.
  * MENTOR -> INTERN : áp dụng ngay (hạ quyền, không cần duyệt) và vẫn ghi lại
    một dòng APPROVED để có vết lịch sử.
  * ADMIN : không dùng cơ chế này.

Người dùng có thể tự rút yêu cầu (CANCELLED) khi nó còn đang PENDING.
"""
import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import pg_enum
from app.models.user import ROLE_ENUM, Role, User


class RoleRequestStatus(str, enum.Enum):
    PENDING = "PENDING"      # đang chờ Admin duyệt
    APPROVED = "APPROVED"    # đã duyệt (hoặc tự áp dụng khi hạ quyền)
    REJECTED = "REJECTED"    # Admin từ chối
    CANCELLED = "CANCELLED"  # người dùng tự rút lại


class RoleChangeRequest(TimestampMixin, Base):
    __tablename__ = "role_change_requests"
    __table_args__ = (
        # Mỗi người chỉ có tối đa MỘT yêu cầu đang chờ. Ràng buộc đặt ở DB (unique
        # index có điều kiện) nên hai request gửi song song cũng không tạo trùng.
        Index(
            "uq_role_change_requests_one_pending",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    # Vai trò lúc gửi yêu cầu, giữ lại để hiển thị "INTERN -> MENTOR" về sau.
    # Dùng lại đúng type object của users.role -> không sinh thêm CREATE TYPE.
    from_role: Mapped[Role] = mapped_column(ROLE_ENUM, nullable=False)
    to_role: Mapped[Role] = mapped_column(ROLE_ENUM, nullable=False)
    status: Mapped[RoleRequestStatus] = mapped_column(
        pg_enum(RoleRequestStatus, "role_request_status"),
        default=RoleRequestStatus.PENDING,
        nullable=False,
    )
    decided_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    user: Mapped[User] = relationship(User, foreign_keys=[user_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RoleChangeRequest id={self.id} user_id={self.user_id} "
            f"{self.from_role.value}->{self.to_role.value} {self.status.value}>"
        )
