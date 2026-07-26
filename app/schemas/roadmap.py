"""Roadmap / Module / module-document schemas."""
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentType
from app.models.enums import Department


class ModuleMetaFields(BaseModel):
    """Course-card metadata for a module (backend-requirements mục 5)."""
    track: Department | None = None
    week_number: int | None = Field(default=None, ge=1)
    duration_text: str | None = Field(
        default=None, max_length=100, description='Free text, e.g. "2 tuần"',
    )
    key_skills: list[str] = []


# ---------- Roadmap ----------
class RoadmapCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class RoadmapUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class RoadmapOut(BaseModel):
    """List item."""
    id: int
    title: str
    description: str | None = None
    module_count: int = 0


# ---------- Roadmap detail (nested) ----------
class LessonInModule(BaseModel):
    module_document_id: int
    document_id: int
    title: str
    type: DocumentType
    position: int


class ModuleWithDocs(ModuleMetaFields):
    id: int
    title: str
    description: str | None = None
    position: int
    documents: list[LessonInModule] = []


class RoadmapDetailOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    modules: list[ModuleWithDocs] = []


# ---------- Module ----------
class ModuleCreate(ModuleMetaFields):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = 0


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    position: int | None = None
    track: Department | None = None
    week_number: int | None = Field(default=None, ge=1)
    duration_text: str | None = Field(default=None, max_length=100)
    # Present (even []) replaces the whole list; null is treated as [].
    key_skills: list[str] | None = None


class ModuleOut(ModuleMetaFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    roadmap_id: int
    title: str
    description: str | None = None
    position: int


# ---------- Assign documents to a module ----------
class AssignDocItem(BaseModel):
    document_id: int
    position: int = 0


class AssignDocsRequest(BaseModel):
    items: list[AssignDocItem] = Field(min_length=1)


class ModuleDocumentOut(BaseModel):
    module_document_id: int
    module_id: int
    document_id: int
    position: int
