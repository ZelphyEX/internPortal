"""Comment schemas (API_SPEC mục 10) — nested replies via parent_comment_id."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class CommentOut(BaseModel):
    id: int
    user: CommentUser
    content: str
    # Optional code attached to the comment (backend-requirements mục 6).
    code_snippet: str | None = None
    # Set by a MENTOR via PATCH /comments/{id}/resolve.
    is_resolved: bool = False
    created_at: datetime
    replies: list["CommentOut"] = []


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    code_snippet: str | None = None
    parent_comment_id: int | None = None


class CommentUpdate(BaseModel):
    """Author-only. `code_snippet` changes only when present (null clears it)."""
    content: str = Field(min_length=1)
    code_snippet: str | None = None


class CommentResolveRequest(BaseModel):
    """PATCH /comments/{id}/resolve body (optional; defaults to resolving)."""
    is_resolved: bool = True


CommentOut.model_rebuild()
