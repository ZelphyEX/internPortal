"""Learning & progress schemas (API_SPEC mục 8)."""
from datetime import datetime

from pydantic import BaseModel

from app.models.assignment import AssignmentStatus
from app.models.document import DocumentType


class MyRoadmapItem(BaseModel):
    """GET /me/roadmaps item."""
    assignment_id: int
    roadmap_id: int
    title: str
    status: AssignmentStatus
    progress_percent: int
    completed_lessons: int
    total_lessons: int


class LessonDetail(BaseModel):
    module_document_id: int
    title: str
    type: DocumentType
    content_url: str
    completed: bool
    completed_at: datetime | None = None


class ModuleWithLessons(BaseModel):
    id: int
    title: str
    position: int
    lessons: list[LessonDetail] = []


class MyRoadmapDetail(BaseModel):
    """GET /me/roadmaps/{assignment_id}."""
    assignment_id: int
    roadmap_id: int
    title: str
    progress_percent: int
    modules: list[ModuleWithLessons] = []


class CompleteRequest(BaseModel):
    assignment_id: int


class CompleteResponse(BaseModel):
    """Returned by mark/unmark so the client can update the progress bar live."""
    module_document_id: int
    completed: bool
    completed_at: datetime | None = None
    progress_percent: int
