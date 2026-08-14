"""Tasks assigned to interns — docs/backend-requirements.md mục 3."""
import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import pg_enum


class TaskStatus(str, enum.Enum):
    """Kanban columns; values are the labels the frontend displays."""
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"
    BLOCKED = "Blocked"


class TaskPriority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable so a mentor can also hand out a task outside any project.
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id"), index=True, nullable=True,
    )
    mentor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, "task_status"), default=TaskStatus.TODO, nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        pg_enum(TaskPriority, "task_priority"), default=TaskPriority.MEDIUM, nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pull-request link submitted by the intern.
    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Mentor-only field (an intern patching this gets 403).
    mentor_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when status becomes DONE, cleared when it leaves DONE. Powers
    # `completed_tasks_this_week` on /dashboard/overview.
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Người nhận task — MỘT task có thể giao cho NHIỀU người (thay cho cột đơn
    # `assigned_intern_id` trước đây, xem migration bỏ cột đó). Đây vẫn là một
    # bản ghi Task duy nhất; ai trong `assignees` sửa (vd đổi status) là sửa
    # chung một task, mọi người còn lại cùng thấy thay đổi ngay.
    assignees: Mapped[list["TaskAssignee"]] = relationship(
        "TaskAssignee", cascade="all, delete-orphan", passive_deletes=True,
        order_by="TaskAssignee.assigned_at",
    )


class TaskAssignee(Base):
    """N-N: người nhận một task. Xem `Task.assignees`."""

    __tablename__ = "task_assignees"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_assignees_task_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
