"""Tag business logic."""
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import DocumentTag, Tag
from app.models.project import ProjectTag


def list_tags(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.name)).all())


def resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    """Load the given tags, or 400 listing the unknown ids.

    Shared by documents and projects (both link to the same `tags` table).
    """
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
    # Remove the join rows first (no ON DELETE CASCADE on the join FKs).
    db.execute(delete(DocumentTag).where(DocumentTag.tag_id == tag_id))
    db.execute(delete(ProjectTag).where(ProjectTag.tag_id == tag_id))
    db.delete(tag)
    db.commit()
