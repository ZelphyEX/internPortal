"""Daily-report schemas (backend-requirements mục 4)."""
from datetime import date as date_, datetime

from pydantic import BaseModel, Field

from app.models.daily_report import DailyReportStatus


class DailyReportOut(BaseModel):
    id: int
    intern_id: int
    intern_name: str | None = None
    date: date_
    completed_today: str
    tomorrow_plan: str | None = None
    blockers: str | None = None
    hours_logged: float | None = None
    status: DailyReportStatus
    mentor_comment: str | None = None
    rating: int | None = None
    reviewed_by: int | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DailyReportCreate(BaseModel):
    """The author is always the caller; `intern_id` is never taken from the body."""
    date: date_
    completed_today: str = Field(min_length=1)
    tomorrow_plan: str | None = None
    blockers: str | None = None
    hours_logged: float | None = Field(default=None, ge=0, le=24)


class DailyReportUpdate(BaseModel):
    """Author-only edit. A report already `Approved` can no longer be edited."""
    date: date_ | None = None
    completed_today: str | None = Field(default=None, min_length=1)
    tomorrow_plan: str | None = None
    blockers: str | None = None
    hours_logged: float | None = Field(default=None, ge=0, le=24)


class DailyReportReview(BaseModel):
    """PATCH /daily-reports/{id}/review (MENTOR/ADMIN)."""
    status: DailyReportStatus = Field(
        description="`Approved` or `Needs Revision` (`Pending` is rejected with 400)",
    )
    mentor_comment: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
