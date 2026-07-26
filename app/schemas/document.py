"""Pydantic schemas for documents & upload."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentType


class UploadResponse(BaseModel):
    content_url: str


class DocumentOut(BaseModel):
    """List item + detail response. `tags` is a list of tag names."""
    id: int
    title: str
    description: str | None = None
    content_url: str
    type: DocumentType
    tags: list[str] = []
    created_at: datetime


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    content_url: str = Field(min_length=1, max_length=1024)
    type: DocumentType
    tag_ids: list[int] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    """PATCH — only provided fields change. tag_ids present (even []) replaces tags."""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    content_url: str | None = Field(default=None, min_length=1, max_length=1024)
    type: DocumentType | None = None
    tag_ids: list[int] | None = None
