"""Dashboard router (API_SPEC mục 9)."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.schemas.dashboard import DashboardMe, DashboardOverview, DashboardRoadmap
from app.services import dashboard_service as svc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/me", response_model=DashboardMe)
def dashboard_me(db: DbSession, current_user: CurrentUser) -> DashboardMe:
    """The caller's own learning summary."""
    return svc.me(db, current_user)


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(db: DbSession, current_user: MentorRequired) -> DashboardOverview:
    return svc.overview(db)


@router.get("/roadmaps/{roadmap_id}", response_model=DashboardRoadmap)
def dashboard_roadmap(
    roadmap_id: int, db: DbSession, current_user: MentorRequired,
) -> DashboardRoadmap:
    return svc.roadmap_progress(db, roadmap_id)
