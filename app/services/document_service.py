"""Document business logic (list/create/get/update/soft-delete + tag linking)."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType, Tag
from app.schemas.document import DocumentCreate, DocumentOut, DocumentUpdate


def _resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    if not tag_ids:
        return []
    tags = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()
    missing = set(tag_ids) - {t.id for t in tags}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tag_ids: {sorted(missing)}",
        )
    return list(tags)


def to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        description=doc.description,
        content_url=doc.content_url,
        type=doc.type,
        tags=[t.name for t in doc.tags],
        created_at=doc.created_at,
    )


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
    )
    doc.tags = _resolve_tags(db, data.tag_ids)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document(db: Session, doc: Document, data: DocumentUpdate) -> Document:
    fields = data.model_dump(exclude_unset=True)
    if "tag_ids" in fields:  # present (even []) -> replace tag links
        doc.tags = _resolve_tags(db, fields.pop("tag_ids") or [])
    for key, value in fields.items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


def soft_delete_document(db: Session, doc: Document) -> None:
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()
