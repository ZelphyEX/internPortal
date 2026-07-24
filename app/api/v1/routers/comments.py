"""Comments router (API_SPEC mục 10)."""
from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.comment import CommentCreate, CommentOut, CommentUpdate
from app.services import comment_service as svc

router = APIRouter(tags=["comments"])


@router.get("/lessons/{module_document_id}/comments", response_model=list[CommentOut])
def list_comments(
    module_document_id: int, db: DbSession, current_user: CurrentUser,
) -> list[CommentOut]:
    return svc.list_comments(db, module_document_id)


@router.post(
    "/lessons/{module_document_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    module_document_id: int, payload: CommentCreate, db: DbSession, current_user: CurrentUser,
) -> CommentOut:
    return svc.create_comment(
        db, current_user, module_document_id, payload.content, payload.parent_comment_id,
    )


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int, payload: CommentUpdate, db: DbSession, current_user: CurrentUser,
) -> CommentOut:
    """Only the author may edit (else 403)."""
    return svc.update_comment(db, current_user, svc.get_comment(db, comment_id), payload.content)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: DbSession, current_user: CurrentUser) -> None:
    """Author or MENTOR/ADMIN may delete (removes the reply subtree)."""
    svc.delete_comment(db, current_user, svc.get_comment(db, comment_id))
