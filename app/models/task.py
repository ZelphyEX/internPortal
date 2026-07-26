"""Tasks assigned to interns — docs/backend-requirements.md mục 3."""
import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
    assigned_intern_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=True,
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
