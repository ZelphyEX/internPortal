"""Tags router (task 1.6 / A6)."""
from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.schemas.tag import TagCreate, TagOut
from app.services import tag_service

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(db: DbSession, current_user: CurrentUser) -> list[TagOut]:
    return tag_service.list_tags(db)


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: DbSession, current_user: MentorRequired) -> TagOut:
    """409 if the tag name already exists (name is UNIQUE)."""
    return tag_service.create_tag(db, payload.name)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: DbSession, current_user: MentorRequired) -> None:
    tag_service.delete_tag(db, tag_id)
