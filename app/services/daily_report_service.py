"""Daily-report business logic (backend-requirements mục 4).

Visibility (CLAUDE.md mục 6): a MENTOR/ADMIN sees every report, an INTERN only
their own. The author is always the authenticated caller — `intern_id` is never
read from the request body. Reviewing (status/comment/rating) is MENTOR/ADMIN.
"""
from datetime import date as date_, datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.daily_report import DailyReport, DailyReportStatus
from app.models.user import Role, User
from app.schemas.daily_report import (
    DailyReportCreate,
    DailyReportOut,
    DailyReportReview,
    DailyReportUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Queries / serialization
# --------------------------------------------------------------------------- #
def list_query(
    *,
    viewer: User,
    intern_id: int | None,
    date_from: date_ | None,
    date_to: date_ | None,
    status_: DailyReportStatus | None,
) -> Select:
    stmt = select(DailyReport)
    if viewer.role == Role.INTERN:
        # Ignore any requested intern_id: an intern only ever sees their own.
        stmt = stmt.where(DailyReport.intern_id == viewer.id)
    elif intern_id is not None:
        stmt = stmt.where(DailyReport.intern_id == intern_id)
    if date_from is not None:
        stmt = stmt.where(DailyReport.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(DailyReport.date <= date_to)
    if status_ is not None:
        stmt = stmt.where(DailyReport.status == status_)
    return stmt.order_by(DailyReport.date.desc(), DailyReport.id.desc())


def to_out_list(db: Session, reports: list[DailyReport]) -> list[DailyReportOut]:
    if not reports:
        return []
    user_ids = {r.intern_id for r in reports}
    user_ids |= {r.reviewed_by for r in reports if r.reviewed_by is not None}
    names = dict(
        db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    )
    return [
        DailyReportOut(
            id=r.id,
            intern_id=r.intern_id,
            intern_name=names.get(r.intern_id),
            date=r.date,
            completed_today=r.completed_today,
            tomorrow_plan=r.tomorrow_plan,
            blockers=r.blockers,
            hours_logged=float(r.hours_logged) if r.hours_logged is not None else None,
            status=r.status,
            mentor_comment=r.mentor_comment,
            rating=r.rating,
            reviewed_by=r.reviewed_by,
            reviewer_name=names.get(r.reviewed_by) if r.reviewed_by else None,
            reviewed_at=r.reviewed_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in reports
    ]


def to_out(db: Session, r: DailyReport) -> DailyReportOut:
    return to_out_list(db, [r])[0]


# --------------------------------------------------------------------------- #
# Access helpers
# --------------------------------------------------------------------------- #
def get_report(db: Session, report_id: int) -> DailyReport:
    r = db.get(DailyReport, report_id)
    if r is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Daily report not found",
        )
    return r


def ensure_can_view(r: DailyReport, viewer: User) -> None:
    if viewer.role == Role.INTERN and r.intern_id != viewer.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This report does not belong to you",
        )


def _ensure_no_report_for_date(
    db: Session, intern_id: int, day: date_, exclude_id: int | None = None,
) -> None:
    stmt = select(DailyReport.id).where(
        DailyReport.intern_id == intern_id, DailyReport.date == day,
    )
    if exclude_id is not None:
        stmt = stmt.where(DailyReport.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="A report for this date already exists",
        )


# --------------------------------------------------------------------------- #
# CRUD + review
# --------------------------------------------------------------------------- #
def create_report(db: Session, author: User, data: DailyReportCreate) -> DailyReport:
    """409 if the caller already reported for that date."""
    _ensure_no_report_for_date(db, author.id, data.date)
    r = DailyReport(
        intern_id=author.id,
        date=data.date,
        completed_today=data.completed_today,
        tomorrow_plan=data.tomorrow_plan,
        blockers=data.blockers,
        hours_logged=data.hours_logged,
        status=DailyReportStatus.PENDING,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# Columns that are NOT NULL: an explicit `null` means "leave unchanged".
_NOT_NULL_FIELDS = ("date", "completed_today")


def update_report(db: Session, r: DailyReport, data: DailyReportUpdate, actor: User) -> DailyReport:
    """Author-only. Refuses to touch an `Approved` report; a report that was
    sent back (`Needs Revision`) returns to `Pending` after the edit."""
    if r.intern_id != actor.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own report",
        )
    if r.status == DailyReportStatus.APPROVED:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="An approved report can no longer be edited",
        )
    fields = data.model_dump(exclude_unset=True)
    for key in _NOT_NULL_FIELDS:
        if key in fields and fields[key] is None:
            fields.pop(key)
    if "date" in fields:
        _ensure_no_report_for_date(db, r.intern_id, fields["date"], exclude_id=r.id)
    for key, value in fields.items():
        setattr(r, key, value)
    if r.status == DailyReportStatus.NEEDS_REVISION:
        r.status = DailyReportStatus.PENDING
        r.reviewed_by = None
        r.reviewed_at = None
    db.commit()
    db.refresh(r)
    return r


def review_report(
    db: Session, r: DailyReport, data: DailyReportReview, reviewer: User,
) -> DailyReport:
    """MENTOR/ADMIN only (enforced by the router)."""
    if data.status == DailyReportStatus.PENDING:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="A review must set status to 'Approved' or 'Needs Revision'",
        )
    r.status = data.status
    fields = data.model_dump(exclude_unset=True)
    if "mentor_comment" in fields:
        r.mentor_comment = fields["mentor_comment"]
    if "rating" in fields:
        r.rating = fields["rating"]
    r.reviewed_by = reviewer.id
    r.reviewed_at = _now()
    db.commit()
    db.refresh(r)
    return r
