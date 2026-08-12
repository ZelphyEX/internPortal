"""Document business logic (list/create/get/update/soft-delete + tag linking)."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType, Tag
from app.schemas.document import DocumentCreate, DocumentOut, DocumentUpdate
from app.services.tag_service import resolve_tags as _resolve_tags


def to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        description=doc.description,
        content_url=doc.content_url,
        type=doc.type,
        categories=doc.categories,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        tags=[t.name for t in doc.tags],
        created_at=doc.created_at,
    )


def _tags_for(db: Session, tag_ids: list[int], tag_names: list[str]) -> list[Tag]:
    """Gộp tag theo id và theo tên. Tên chưa có thì tạo mới (không phân biệt hoa
    thường ở phần so khớp) — nhờ vậy client chỉ cần gửi tên, khỏi gọi POST /tags."""
    tags = list(_resolve_tags(db, tag_ids))
    seen = {t.name.lower() for t in tags}
    for raw in tag_names:
        name = raw.strip()
        if not name or name.lower() in seen:
            continue
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()  # cần id trước khi gắn vào document_tags
        tags.append(tag)
        seen.add(name.lower())
    return tags


def list_query(
    *, search: str | None, tag: str | None, type_: DocumentType | None,
) -> Select:
    stmt = select(Document).where(Document.deleted_at.is_(None))
    if search:
        stmt = stmt.where(Document.title.ilike(f"%{search}%"))
    if type_ is not None:
        stmt = stmt.where(Document.type == type_)
    if tag:
        stmt = stmt.join(Document.tags).where(Tag.name == tag)
    return stmt.order_by(Document.created_at.desc(), Document.id.desc())


def get_document(db: Session, doc_id: int) -> Document:
    doc = db.scalar(
        select(Document).where(Document.id == doc_id, Document.deleted_at.is_(None))
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def create_document(db: Session, data: DocumentCreate) -> Document:
    doc = Document(
        title=data.title,
        description=data.description,
        content_url=data.content_url,
        type=data.type,
        categories=data.categories,
        file_type=data.file_type,
        file_size_bytes=data.file_size_bytes,
    )
    doc.tags = _tags_for(db, data.tag_ids, data.tag_names)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document(db: Session, doc: Document, data: DocumentUpdate) -> Document:
    fields = data.model_dump(exclude_unset=True)
    # tag_ids / tag_names có mặt (kể cả []) -> thay toàn bộ tag của tài liệu.
    if "tag_ids" in fields or "tag_names" in fields:
        doc.tags = _tags_for(
            db, fields.pop("tag_ids", None) or [], fields.pop("tag_names", None) or [],
        )
    for key, value in fields.items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


def soft_delete_document(db: Session, doc: Document) -> None:
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()
