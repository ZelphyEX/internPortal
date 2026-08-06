"""Roadmaps / Modules / module-documents router (API_SPEC mục 6)."""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.schemas.common import Page
from app.schemas.roadmap import (
    AttachDocRequest,
    AssignDocsRequest,
    LessonAttachmentOut,
    LessonCreate,
    LessonUpdate,
    ModuleCreate,
    ModuleDocumentOut,
    ModuleOut,
    ModuleUpdate,
    RoadmapCreate,
    RoadmapDetailOut,
    RoadmapOut,
    RoadmapUpdate,
)
from app.services import roadmap_service as svc

router = APIRouter(tags=["roadmaps"])


# ---------- Roadmaps ----------
@router.get("/roadmaps", response_model=Page[RoadmapOut])
def list_roadmaps(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in title")] = None,
) -> Page[RoadmapOut]:
    rows, total, pages = paginate(db, svc.list_query(search=search), page=page, size=size)
    counts = svc.module_counts(db, [r.id for r in rows])
    return Page(
        items=[svc.to_roadmap_out(r, counts.get(r.id, 0)) for r in rows],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("/roadmaps", response_model=RoadmapOut, status_code=status.HTTP_201_CREATED)
def create_roadmap(payload: RoadmapCreate, db: DbSession, current_user: MentorRequired) -> RoadmapOut:
    r = svc.create_roadmap(db, payload)
    return svc.to_roadmap_out(r, 0)


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapDetailOut)
def get_roadmap(roadmap_id: int, db: DbSession, current_user: CurrentUser) -> RoadmapDetailOut:
    return svc.get_roadmap_detail(db, roadmap_id)


@router.patch("/roadmaps/{roadmap_id}", response_model=RoadmapOut)
def update_roadmap(
    roadmap_id: int, payload: RoadmapUpdate, db: DbSession, current_user: MentorRequired,
) -> RoadmapOut:
    r = svc.update_roadmap(db, svc.get_roadmap(db, roadmap_id), payload)
    counts = svc.module_counts(db, [r.id])
    return svc.to_roadmap_out(r, counts.get(r.id, 0))


@router.delete("/roadmaps/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_roadmap(roadmap_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_roadmap(db, svc.get_roadmap(db, roadmap_id))


# ---------- Modules ----------
@router.post(
    "/roadmaps/{roadmap_id}/modules",
    response_model=ModuleOut,
    status_code=status.HTTP_201_CREATED,
)
def add_module(
    roadmap_id: int, payload: ModuleCreate, db: DbSession, current_user: MentorRequired,
) -> ModuleOut:
    return svc.add_module(db, roadmap_id, payload)


@router.patch("/modules/{module_id}", response_model=ModuleOut)
def update_module(
    module_id: int, payload: ModuleUpdate, db: DbSession, current_user: MentorRequired,
) -> ModuleOut:
    return svc.update_module(db, svc.get_module(db, module_id), payload)


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(module_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_module(db, svc.get_module(db, module_id))


# ---------- module-documents (assign / remove) ----------
@router.post(
    "/modules/{module_id}/documents",
    response_model=list[ModuleDocumentOut],
    status_code=status.HTTP_201_CREATED,
)
def assign_documents(
    module_id: int, payload: AssignDocsRequest, db: DbSession, current_user: MentorRequired,
) -> list[ModuleDocumentOut]:
    return svc.assign_documents(db, module_id, payload.items)


@router.delete("/module-documents/{module_document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_module_document(
    module_document_id: int, db: DbSession, current_user: MentorRequired,
) -> None:
    """Xoá một bài học khỏi chặng (không xoá tài liệu gốc trong Thư viện)."""
    svc.delete_module_document(db, svc.get_module_document(db, module_document_id))


# ---------- Bài học tạo tay (tên + link) ----------
@router.post(
    "/modules/{module_id}/lessons",
    response_model=ModuleDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_lesson(
    module_id: int, payload: LessonCreate, db: DbSession, current_user: MentorRequired,
) -> ModuleDocumentOut:
    """Tạo bài học bằng **tên + link** (video/bài giảng).

    Khác `POST /modules/{id}/documents` (gán tài liệu có sẵn từ Thư viện):
    bài học tạo ở đây không sinh bản ghi nào trong Thư viện Tài liệu.
    """
    return svc.create_lesson(db, module_id, payload)


@router.patch("/module-documents/{module_document_id}", response_model=ModuleDocumentOut)
def update_lesson(
    module_document_id: int,
    payload: LessonUpdate,
    db: DbSession,
    current_user: MentorRequired,
) -> ModuleDocumentOut:
    """Sửa tên / link / thứ tự của một bài học."""
    md = svc.get_module_document(db, module_document_id)
    return svc.update_lesson(db, md, payload)


# ---------- Tài liệu đính kèm dưới bài học ----------
@router.post(
    "/module-documents/{module_document_id}/attachments",
    response_model=list[LessonAttachmentOut],
    status_code=status.HTTP_201_CREATED,
)
def attach_documents(
    module_document_id: int,
    payload: AttachDocRequest,
    db: DbSession,
    current_user: MentorRequired,
) -> list[LessonAttachmentOut]:
    """Đính tài liệu (từ Thư viện) vào một bài học — hiển thị ngay dưới bài học.
    Tài liệu đã đính sẽ được bỏ qua, không báo lỗi."""
    md = svc.get_module_document(db, module_document_id)
    return svc.attach_documents(db, md, payload.document_ids)


@router.delete(
    "/module-documents/{module_document_id}/attachments/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_document(
    module_document_id: int,
    document_id: int,
    db: DbSession,
    current_user: MentorRequired,
) -> None:
    """Gỡ tài liệu khỏi bài học (không xoá tài liệu gốc)."""
    svc.get_module_document(db, module_document_id)  # 404 nếu bài học không tồn tại
    svc.detach_document(db, module_document_id, document_id)
