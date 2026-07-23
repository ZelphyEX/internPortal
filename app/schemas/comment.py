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
    created_at: datetime
    replies: list["CommentOut"] = []


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    parent_comment_id: int | None = None


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1)


CommentOut.model_rebuild()
