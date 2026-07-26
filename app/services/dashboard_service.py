"""Dashboard aggregation logic (API_SPEC mục 9).

`/dashboard/me` is self-only (uses the caller's assignments). The MENTOR
endpoints aggregate across everyone. Progress % is computed live via
`app.services.progress` so the numbers match the learning views.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import AssignmentStatus, RoadmapAssignment
from app.models.daily_report import DailyReport, DailyReportStatus
from app.models.group import Group
from app.models.roadmap import Roadmap
from app.models.task import Task, TaskStatus
from app.models.user import Role, User, UserStatus
from app.schemas.dashboard import (
    DashboardMe,
    DashboardOverview,
    DashboardRoadmap,
    GroupProgress,
    InternProgress,
    MyRoadmapMini,
)
from app.services import learning_service, progress


def _avg(values: list[int]) -> int:
    return int(round(sum(values) / len(values))) if values else 0


def _week_start() -> datetime:
    """Monday 00:00 UTC of the current week."""
    now = datetime.now(timezone.utc)
    return datetime.combine(
        (now - timedelta(days=now.weekday())).date(), time.min, tzinfo=timezone.utc,
    )


def _my_task_completion_percent(db: Session, user_id: int) -> int:
    total = db.scalar(
        select(func.count(Task.id)).where(Task.assigned_intern_id == user_id)
    ) or 0
    if total == 0:
        return 0
    done = db.scalar(
        select(func.count(Task.id)).where(
            Task.assigned_intern_id == user_id, Task.status == TaskStatus.DONE,
        )
    ) or 0
    return progress.percent(done, total)


def me(db: Session, user: User) -> DashboardMe:
    items = learning_service.list_my_roadmaps(db, user)
    completed = sum(1 for i in items if i.status == AssignmentStatus.COMPLETED)
    pending_reports = db.scalar(
        select(func.count(DailyReport.id)).where(
            DailyReport.intern_id == user.id,
            DailyReport.status == DailyReportStatus.PENDING,
        )
    ) or 0
    return DashboardMe(
        total_roadmaps=len(items),
        completed_roadmaps=completed,
        overall_progress_percent=_avg([i.progress_percent for i in items]),
        task_completion_percent=_my_task_completion_percent(db, user.id),
        pending_reports_count=pending_reports,
        roadmaps=[
            MyRoadmapMini(
                assignment_id=i.assignment_id, title=i.title,
                progress_percent=i.progress_percent,
            )
            for i in items
        ],
    )


def overview(db: Session) -> DashboardOverview:
    total_interns = db.scalar(
        select(func.count(User.id)).where(
            User.role == Role.INTERN,
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    ) or 0
    active = db.scalar(
        select(func.count(RoadmapAssignment.id)).where(
            RoadmapAssignment.status == AssignmentStatus.IN_PROGRESS
        )
    ) or 0
    done = db.scalar(
        select(func.count(RoadmapAssignment.id)).where(
            RoadmapAssignment.status == AssignmentStatus.COMPLETED
        )
    ) or 0

    # Average progress per group (only assignments made via a group count).
    groups = list(db.scalars(select(Group).order_by(Group.id)).all())
    group_assigns = list(
        db.scalars(
            select(RoadmapAssignment).where(
                RoadmapAssignment.source_group_id.is_not(None)
            )
        ).all()
    )
    totals = progress.total_lessons_map(db, {a.roadmap_id for a in group_assigns})
    completed = progress.completed_counts(db, [a.id for a in group_assigns])
    per_group: dict[int, list[int]] = defaultdict(list)
    for a in group_assigns:
        per_group[a.source_group_id].append(
            progress.percent(completed.get(a.id, 0), totals.get(a.roadmap_id, 0))
        )
    by_group = [
        GroupProgress(
            group_id=g.id, name=g.name,
            avg_progress_percent=_avg(per_group.get(g.id, [])),
        )
        for g in groups
    ]

    # --- backend-requirements mục 7 ---
    avg_score = db.scalar(
        select(func.avg(User.score)).where(
            User.role == Role.INTERN,
            User.deleted_at.is_(None),
            User.score.is_not(None),
        )
    )
    tasks_this_week = db.scalar(
        select(func.count(Task.id)).where(
            Task.status == TaskStatus.DONE,
            Task.completed_at.is_not(None),
            Task.completed_at >= _week_start(),
        )
    ) or 0
    pending_reviews = db.scalar(
        select(func.count(DailyReport.id)).where(
            DailyReport.status == DailyReportStatus.PENDING
        )
    ) or 0

    return DashboardOverview(
        total_interns=total_interns,
        active_assignments=active,
        completed_assignments=done,
        avg_score=round(float(avg_score), 2) if avg_score is not None else 0,
        completed_tasks_this_week=tasks_this_week,
        pending_reviews_count=pending_reviews,
        by_group=by_group,
    )


def roadmap_progress(db: Session, roadmap_id: int) -> DashboardRoadmap:
    roadmap = db.get(Roadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    rows = list(
        db.execute(
            select(RoadmapAssignment, User.full_name)
            .join(User, User.id == RoadmapAssignment.user_id)
            .where(RoadmapAssignment.roadmap_id == roadmap_id)
            .order_by(User.full_name, User.id)
        ).all()
    )
    total = progress.total_lessons(db, roadmap_id)
    completed = progress.completed_counts(db, [a.id for a, _ in rows])
    interns = [
        InternProgress(
            user_id=a.user_id,
            full_name=full_name,
            progress_percent=progress.percent(completed.get(a.id, 0), total),
            status=a.status,
        )
        for a, full_name in rows
    ]
    return DashboardRoadmap(roadmap_id=roadmap.id, title=roadmap.title, interns=interns)
