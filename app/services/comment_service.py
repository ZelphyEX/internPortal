"""Comment business logic (API_SPEC mục 10).

Threading: a comment may reference a parent (same lesson) for nested replies.
Permissions: only the author may edit; the author OR a MENTOR/ADMIN may delete;
only a MENTOR/ADMIN may resolve (`is_resolved`).
Deleting a comment removes its whole reply subtree.
"""
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.comment import Comment
from app.models.roadmap import ModuleDocument
from app.models.user import Role, User
from app.schemas.comment import CommentOut, CommentUpdate, CommentUser


def _to_out(c: Comment, full_name: str) -> CommentOut:
    """Serialize one comment (replies are attached by the caller)."""
    return CommentOut(
        id=c.id,
        user=CommentUser(id=c.user_id, full_name=full_name),
        content=c.content,
        code_snippet=c.code_snippet,
        is_resolved=c.is_resolved,
        created_at=c.created_at,
        replies=[],
    )


def _ensure_lesson(db: Session, module_document_id: int) -> None:
    if db.get(ModuleDocument, module_document_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")


def get_comment(db: Session, comment_id: int) -> Comment:
    c = db.get(Comment, comment_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return c


def list_comments(db: Session, module_document_id: int) -> list[CommentOut]:
    """Return top-level comments with nested replies (chronological)."""
    _ensure_lesson(db, module_document_id)
    rows = db.execute(
        select(Comment, User.full_name)
        .join(User, User.id == Comment.user_id)
        .where(Comment.module_document_id == module_document_id)
        .order_by(Comment.created_at, Comment.id)
    ).all()

    nodes: dict[int, CommentOut] = {c.id: _to_out(c, full_name) for c, full_name in rows}
    roots: list[CommentOut] = []
    for c, _ in rows:
        node = nodes[c.id]
        parent = nodes.get(c.parent_comment_id) if c.parent_comment_id else None
        if parent is not None:
            parent.replies.append(node)
        else:
            roots.append(node)
    return roots


def create_comment(
    db: Session, user: User, module_document_id: int,
    content: str, parent_comment_id: int | None, code_snippet: str | None = None,
) -> CommentOut:
    _ensure_lesson(db, module_document_id)
    if parent_comment_id is not None:
        parent = db.get(Comment, parent_comment_id)
        if parent is None or parent.module_document_id != module_document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_comment_id is invalid for this lesson",
            )
    c = Comment(
        module_document_id=module_document_id,
        user_id=user.id,
        content=content,
        code_snippet=code_snippet,
        parent_comment_id=parent_comment_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c, user.full_name)


def update_comment(
    db: Session, user: User, comment: Comment, data: CommentUpdate,
) -> CommentOut:
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own comment",
        )
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(comment, key, value)
    db.commit()
    db.refresh(comment)
    return _to_out(comment, user.full_name)


def set_resolved(db: Session, comment: Comment, is_resolved: bool) -> CommentOut:
    """MENTOR/ADMIN only (enforced by the router) — separate from editing."""
    comment.is_resolved = is_resolved
    db.commit()
    db.refresh(comment)
    author_name = db.scalar(select(User.full_name).where(User.id == comment.user_id)) or ""
    return _to_out(comment, author_name)


def delete_comment(db: Session, user: User, comment: Comment) -> None:
    """Author or MENTOR/ADMIN only. Removes the comment and its reply subtree."""
    is_mentor = user.role in (Role.MENTOR, Role.ADMIN)
    if comment.user_id != user.id and not is_mentor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author or a mentor can delete this comment",
        )
    # Build the parent -> children map for this lesson, then collect the subtree.
    rows = db.execute(
        select(Comment.id, Comment.parent_comment_id).where(
            Comment.module_document_id == comment.module_document_id
        )
    ).all()
    children: dict[int, list[int]] = {}
    for cid, pid in rows:
        children.setdefault(pid, []).append(cid)

    order: list[int] = []  # preorder: parent before descendants
    stack = [comment.id]
    while stack:
        cur = stack.pop()
        order.append(cur)
        stack.extend(children.get(cur, []))
    # Delete descendants before ancestors to satisfy the self-referential FK.
    # Use explicit Core DELETEs (executed in this exact order) rather than ORM
    # db.delete(), whose unit-of-work would reorder/batch the deletes and could
    # try to remove a parent before its replies -> ForeignKeyViolation.
    for cid in reversed(order):
        db.execute(delete(Comment).where(Comment.id == cid))
    db.commit()
