"""Project schemas (backend-requirements mục 2)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department
from app.models.project import ProjectStatus


class ProjectMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str  # response side — not re-validated (see schemas/user.py)
    avatar_url: str | None = None


class ProjectOut(BaseModel):
    """List item. `tags` is a list of tag names; `lead_name` resolves lead_user_id."""
    id: int
    code: str
    title: str
    department: Department | None = None
    status: ProjectStatus
    lead_user_id: int | None = None
    lead_name: str | None = None
    progress_percent: int
    deadline: date | None = None
    description: str | None = None
    tags: list[str] = []
    member_count: int = 0
    created_at: datetime


class ProjectDetailOut(ProjectOut):
    """Detail — includes the member list."""
    members: list[ProjectMemberOut] = []


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    department: Department | None = None
    status: ProjectStatus = ProjectStatus.IN_PLANNING
    lead_user_id: int | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    deadline: date | None = None
    description: str | None = None
    tag_ids: list[int] = Field(default_factory=list)
    # Optional: seed the member list on creation.
    member_ids: list[int] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """PATCH — only provided fields change. `tag_ids` present (even []) replaces tags."""
    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    department: Department | None = None
    status: ProjectStatus | None = None
    lead_user_id: int | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    deadline: date | None = None
    description: str | None = None
    tag_ids: list[int] | None = None


class AddProjectMembersRequest(BaseModel):
    """Bulk add. Duplicates (already in the project) and unknown ids are skipped."""
    user_ids: list[int] = Field(min_length=1)
