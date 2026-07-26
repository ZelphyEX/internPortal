"""Roadmap assignments + per-lesson progress."""
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssignmentStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class RoadmapAssignment(Base):
    """One assignment of a roadmap to a user. `id` == assignment_id."""
    __tablename__ = "roadmap_assignments"
    __table_args__ = (
        UniqueConstraint("roadmap_id", "user_id", name="uq_roadmap_assignments_roadmap_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roadmaps.id"), index=True, nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status", values_callable=lambda e: [m.value for m in e]),
        default=AssignmentStatus.IN_PROGRESS,
        nullable=False,
    )
    # Set when assigned via a group (POST /roadmaps/{id}/assign-group).
    source_group_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("groups.id"), nullable=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "module_document_id",
            name="uq_lesson_progress_assignment_moduledoc",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roadmap_assignments.id"), index=True, nullable=False,
    )
    module_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("module_documents.id"), index=True, nullable=False,
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
