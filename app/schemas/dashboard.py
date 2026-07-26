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
    # backend-requirements mục 7 — 0 when the intern has no task assigned.
    task_completion_percent: int = 0
    # Own reports still waiting for a mentor review (status = Pending).
    pending_reports_count: int = 0
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
    # backend-requirements mục 7.
    # Average `users.score` over active interns that have one (0 if none).
    avg_score: float = 0
    # Tasks moved to Done since Monday 00:00 UTC of the current week.
    completed_tasks_this_week: int = 0
    # Daily reports waiting for a review (status = Pending), all interns.
    pending_reviews_count: int = 0
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
