"""Projects (Dự án) + members + tags — docs/backend-requirements.md mục 2."""
import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import DEPARTMENT_ENUM, Department, pg_enum


class ProjectStatus(str, enum.Enum):
    """Values are the labels the frontend displays."""
    IN_PLANNING = "In Planning"
    ACTIVE = "Active"
    UNDER_REVIEW = "Under Review"
    COMPLETED = "Completed"


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Human-readable identifier shown on the board, e.g. "PRJ-001".
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Department | None] = mapped_column(DEPARTMENT_ENUM, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        pg_enum(ProjectStatus, "project_status"),
        default=ProjectStatus.IN_PLANNING,
        nullable=False,
    )
    lead_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=True,
    )
    # Maintained by the mentor (0..100) — NOT derived from tasks; the
    # task-based number is `task_completion_percent` on /dashboard/me.
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Soft delete: tasks keep referencing the project, so rows are never
    # physically removed.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reuses the shared `tags` table (same pattern as documents).
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821  (app.models.document.Tag)
        secondary="project_tags", lazy="selectin", order_by="Tag.name",
    )


class ProjectMember(Base):
    """N-N users <-> projects."""
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id"), index=True, nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    # Nhóm đã kéo người này vào dự án (NULL = được thêm lẻ).
    # Nhờ cột này, gán một NHÓM vào dự án trở thành "luật thường trực": ai vào nhóm
    # sau cũng tự được thêm, và khi rời nhóm chỉ gỡ đúng những người vào bằng nhóm.
    # Đối xứng với `roadmap_assignments.source_group_id`.
    source_group_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("groups.id"), index=True, nullable=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class ProjectTag(Base):
    """N-N join; composite PK (project_id, tag_id)."""
    __tablename__ = "project_tags"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id"), primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tags.id"), primary_key=True,
    )
