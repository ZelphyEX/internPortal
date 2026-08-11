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
    #: Danh mục trong Thư viện Tài liệu (Onboarding / AI / Coding Standard...).
    category: str | None = None
    #: Định dạng thật: PDF | DOCX | SLIDE | MD. `type` không biểu diễn được đủ.
    file_type: str | None = None
    file_size_bytes: int | None = None
    tags: list[str] = []
    created_at: datetime


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    content_url: str = Field(min_length=1, max_length=1024)
    type: DocumentType
    category: str | None = Field(default=None, max_length=100)
    file_type: str | None = Field(default=None, max_length=20)
    file_size_bytes: int | None = Field(default=None, ge=0)
    tag_ids: list[int] = Field(default_factory=list)
    #: Tên tag dạng chữ (tạo mới nếu chưa có). Tiện hơn `tag_ids` cho client vì
    #: không phải gọi trước `POST /tags` để lấy id.
    tag_names: list[str] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    """PATCH — only provided fields change. tag_ids present (even []) replaces tags."""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    content_url: str | None = Field(default=None, min_length=1, max_length=1024)
    type: DocumentType | None = None
    category: str | None = Field(default=None, max_length=100)
    file_type: str | None = Field(default=None, max_length=20)
    file_size_bytes: int | None = Field(default=None, ge=0)
    tag_ids: list[int] | None = None
    tag_names: list[str] | None = None
