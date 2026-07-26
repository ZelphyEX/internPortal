"""User model + role/status enums."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import DEPARTMENT_ENUM, Department


class Role(str, enum.Enum):
    """Role hierarchy: ADMIN > MENTOR > INTERN (see app.core.deps.require_role)."""
    ADMIN = "ADMIN"
    MENTOR = "MENTOR"
    INTERN = "INTERN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=Role.INTERN,
        nullable=False,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Soft delete: set instead of physically removing the row.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ----------------------------------------------------------------------- #
    # Intern profile (docs/backend-requirements.md mục 1).
    # All nullable: only meaningful for role=INTERN, and filled in by a
    # MENTOR/ADMIN via PATCH /users/{id}/profile.
    # ----------------------------------------------------------------------- #
    department: Mapped[Department | None] = mapped_column(DEPARTMENT_ENUM, nullable=True)
    # The mentor in charge of this intern (self-referencing FK).
    mentor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    university: Mapped[str | None] = mapped_column(String(255), nullable=True)
    major: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Evaluation score and attendance rate (%), both 0..100.
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    attendance_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
