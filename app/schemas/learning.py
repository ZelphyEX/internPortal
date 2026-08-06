"""Learning & progress schemas (API_SPEC mục 8)."""
from datetime import datetime

from pydantic import BaseModel

from app.models.assignment import AssignmentStatus
from app.models.document import DocumentType
from app.schemas.roadmap import LessonAttachmentOut, ModuleMetaFields


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
    #: None với bài học tạo tay (không gắn tài liệu nào trong Thư viện).
    type: DocumentType | None = None
    #: Link mở khi Intern bấm vào tên bài học.
    content_url: str | None = None
    completed: bool
    completed_at: datetime | None = None
    #: Tài liệu đính kèm hiển thị ngay dưới bài học.
    attachments: list[LessonAttachmentOut] = []


class ModuleWithLessons(ModuleMetaFields):
    """A module as the intern sees it (course card + its lessons)."""
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
