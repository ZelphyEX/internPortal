"""Daily reports written by interns — docs/backend-requirements.md mục 4."""
import enum
from datetime import date as date_, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import pg_enum


class DailyReportStatus(str, enum.Enum):
    """Values are the labels the frontend displays."""
    PENDING = "Pending"
    APPROVED = "Approved"
    NEEDS_REVISION = "Needs Revision"


class DailyReport(TimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        # One report per intern per day.
        UniqueConstraint("intern_id", "date", name="uq_daily_reports_intern_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intern_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)
    completed_today: Mapped[str] = mapped_column(Text, nullable=False)
    tomorrow_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours_logged: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)

    # ----- review (mentor) -----
    status: Mapped[DailyReportStatus] = mapped_column(
        pg_enum(DailyReportStatus, "daily_report_status"),
        default=DailyReportStatus.PENDING,
        nullable=False,
    )
    mentor_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..5
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
