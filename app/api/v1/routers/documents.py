"""Documents router: upload (task 1.3) + CRUD with tag filter/search/pagination (task 1.5)."""
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.models.document import DocumentType
from app.schemas.common import Page
from app.schemas.document import DocumentCreate, DocumentOut, DocumentUpdate, UploadResponse
from app.services import document_service
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in title")] = None,
    tag: Annotated[str | None, Query(description="filter by tag name")] = None,
    type: Annotated[DocumentType | None, Query()] = None,
) -> Page[DocumentOut]:
    stmt = document_service.list_query(search=search, tag=tag, type_=type)
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(
        items=[document_service.to_out(d) for d in rows],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate, db: DbSession, current_user: MentorRequired,
) -> DocumentOut:
    doc = document_service.create_document(db, payload)
    return document_service.to_out(doc)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file to storage; returns its content_url",
)
async def upload_file(
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="File to upload (PDF, image, ...)")],
) -> UploadResponse:
    """Any authenticated user may upload (MENTOR: documents; INTERN/MENTOR:
    avatar images). Returns a `content_url` for documents.content_url / users.avatar_url."""
    data = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.MAX_UPLOAD_MB} MB)",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    url = get_storage().save(
        data, original_filename=file.filename, content_type=file.content_type,
    )
    return UploadResponse(content_url=url)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: DbSession, current_user: CurrentUser) -> DocumentOut:
    return document_service.to_out(document_service.get_document(db, document_id))


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int, payload: DocumentUpdate, db: DbSession, current_user: MentorRequired,
) -> DocumentOut:
    doc = document_service.get_document(db, document_id)
    return document_service.to_out(document_service.update_document(db, doc, payload))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: DbSession, current_user: MentorRequired) -> None:
    """Soft delete (sets deleted_at)."""
    doc = document_service.get_document(db, document_id)
    document_service.soft_delete_document(db, doc)
