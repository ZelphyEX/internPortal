"""Task schemas (backend-requirements mục 3)."""
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskStatus


class TaskOut(BaseModel):
    id: int
    title: str
    project_id: int | None = None
    project_code: str | None = None
    project_title: str | None = None
    assigned_intern_id: int | None = None
    assigned_intern_name: str | None = None
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
    assigned_intern_id: int | None = None
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
    field in the payload is rejected with 403.
    """
    title: str | None = Field(default=None, min_length=1, max_length=255)
    project_id: int | None = None
    assigned_intern_id: int | None = None
    mentor_id: int | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    description: str | None = None
    pr_url: str | None = Field(default=None, max_length=1024)
    mentor_feedback: str | None = None
