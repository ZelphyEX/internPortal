"""Daily-reports router (backend-requirements mục 4).

An INTERN writes their own report and only ever sees their own; a MENTOR/ADMIN
sees everything and reviews (approve / send back).
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.models.daily_report import DailyReportStatus
from app.schemas.common import Page
from app.schemas.daily_report import (
    DailyReportCreate,
    DailyReportOut,
    DailyReportReview,
    DailyReportUpdate,
)
from app.services import daily_report_service as svc

router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])


@router.get("", response_model=Page[DailyReportOut])
def list_daily_reports(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    intern_id: Annotated[
        int | None, Query(description="MENTOR only; an intern always gets their own")
    ] = None,
    date_from: Annotated[date | None, Query(description="inclusive lower bound")] = None,
    date_to: Annotated[date | None, Query(description="inclusive upper bound")] = None,
    status_: Annotated[DailyReportStatus | None, Query(alias="status")] = None,
) -> Page[DailyReportOut]:
    stmt = svc.list_query(
        viewer=current_user, intern_id=intern_id,
        date_from=date_from, date_to=date_to, status_=status_,
    )
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(
        items=svc.to_out_list(db, list(rows)),
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=DailyReportOut, status_code=status.HTTP_201_CREATED)
def create_daily_report(
    payload: DailyReportCreate, db: DbSession, current_user: CurrentUser,
) -> DailyReportOut:
    """The report belongs to the caller. 409 if they already reported that date."""
    return svc.to_out(db, svc.create_report(db, current_user, payload))


@router.get("/{report_id}", response_model=DailyReportOut)
def get_daily_report(
    report_id: int, db: DbSession, current_user: CurrentUser,
) -> DailyReportOut:
    r = svc.get_report(db, report_id)
    svc.ensure_can_view(r, current_user)
    return svc.to_out(db, r)


@router.patch("/{report_id}", response_model=DailyReportOut)
def update_daily_report(
    report_id: int, payload: DailyReportUpdate, db: DbSession, current_user: CurrentUser,
) -> DailyReportOut:
    """Author only. 400 once the report is `Approved`; a report in
    `Needs Revision` goes back to `Pending` after the edit."""
    r = svc.get_report(db, report_id)
    return svc.to_out(db, svc.update_report(db, r, payload, current_user))


@router.patch("/{report_id}/review", response_model=DailyReportOut)
def review_daily_report(
    report_id: int, payload: DailyReportReview, db: DbSession, current_user: MentorRequired,
) -> DailyReportOut:
    """MENTOR/ADMIN. Set `Approved` / `Needs Revision` (+ comment, rating 1-5)."""
    r = svc.get_report(db, report_id)
    return svc.to_out(db, svc.review_report(db, r, payload, current_user))
