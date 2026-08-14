"""Task schemas (backend-requirements mục 3)."""
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskStatus


class TaskAssigneeOut(BaseModel):
    user_id: int
    full_name: str


class TaskOut(BaseModel):
    id: int
    title: str
    project_id: int | None = None
    project_code: str | None = None
    project_title: str | None = None
    # Một task có thể giao cho NHIỀU người — đây vẫn là MỘT task duy nhất, ai
    # trong danh sách sửa (status, PR url...) là sửa chung, không tách task riêng.
    assignees: list[TaskAssigneeOut] = []
    mentor_id: int | None = None
    mentor_name: str | None = None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None = None
    description: str | None = None
    pr_url: str | None = None
    mentor_feedback: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    project_id: int | None = None
    # 0, 1, hoặc nhiều người — vd giao cả nhóm/dự án cho cùng một task này.
    assigned_intern_ids: list[int] = Field(default_factory=list, max_length=500)
    # Defaults to the caller when omitted.
    mentor_id: int | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    description: str | None = None
    pr_url: str | None = Field(default=None, max_length=1024)


class TaskUpdate(BaseModel):
    """PATCH — only provided fields change.

    An INTERN may only patch `status` and `pr_url` on their own task; any other
    field in the payload — kể cả `assigned_intern_ids` — is rejected with 403.
    """
    title: str | None = Field(default=None, min_length=1, max_length=255)
    project_id: int | None = None
    # Gửi field này là THAY TOÀN BỘ danh sách người nhận (không phải thêm/gộp).
    assigned_intern_ids: list[int] | None = Field(default=None, max_length=500)
    mentor_id: int | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    description: str | None = None
    pr_url: str | None = Field(default=None, max_length=1024)
    mentor_feedback: str | None = None
