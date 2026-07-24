"""Roadmap-assignment schemas (API_SPEC mục 7)."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.assignment import AssignmentStatus


class AssignRequest(BaseModel):
    """POST /roadmaps/{id}/assign — one or more interns."""
    user_ids: list[int] = Field(min_length=1)


class AssignCreatedItem(BaseModel):
    assignment_id: int
    user_id: int


class AssignResponse(BaseModel):
    created: list[AssignCreatedItem] = []


class AssignGroupRequest(BaseModel):
    group_id: int


class AssignGroupResponse(BaseModel):
    group_id: int
    assigned_count: int
    skipped_existing: int


class AssignmentListItem(BaseModel):
    """GET /roadmap-assignments item (progress computed live)."""
    assignment_id: int
    roadmap_id: int
    roadmap_title: str
    user_id: int
    user_name: str
    status: AssignmentStatus
    progress_percent: int
    assigned_at: datetime
