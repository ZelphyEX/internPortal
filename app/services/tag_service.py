"""Tag business logic."""
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import DocumentTag, Tag


def list_tags(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.name)).all())


def create_tag(db: Session, name: str) -> Tag:
    if db.scalar(select(Tag).where(Tag.name == name)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    # Remove document<->tag links first (no ON DELETE CASCADE on the join FK).
    db.execute(delete(DocumentTag).where(DocumentTag.tag_id == tag_id))
    db.delete(tag)
    db.commit()
