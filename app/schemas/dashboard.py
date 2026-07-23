"""Dashboard schemas (API_SPEC mục 9)."""
from pydantic import BaseModel

from app.models.assignment import AssignmentStatus


# ---------- /dashboard/me ----------
class MyRoadmapMini(BaseModel):
    assignment_id: int
    title: str
    progress_percent: int


class DashboardMe(BaseModel):
    total_roadmaps: int
    completed_roadmaps: int
    overall_progress_percent: int
    roadmaps: list[MyRoadmapMini] = []


# ---------- /dashboard/overview ----------
class GroupProgress(BaseModel):
    group_id: int
    name: str
    avg_progress_percent: int


class DashboardOverview(BaseModel):
    total_interns: int
    active_assignments: int
    completed_assignments: int
    by_group: list[GroupProgress] = []


# ---------- /dashboard/roadmaps/{id} ----------
class InternProgress(BaseModel):
    user_id: int
    full_name: str
    progress_percent: int
    status: AssignmentStatus


class DashboardRoadmap(BaseModel):
    roadmap_id: int
    title: str
    interns: list[InternProgress] = []
