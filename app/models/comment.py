"""Comments on a lesson (module_document), with self-referential replies."""
from sqlalchemy import BigInteger, Boolean, ForeignKey, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("module_documents.id"), index=True, nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional code attached to the question/discussion (frontend renders it in
    # a code block) — docs/backend-requirements.md mục 6.
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Marked by a MENTOR via PATCH /comments/{id}/resolve (a different
    # permission from editing the content, which stays author-only).
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false(),
    )
    # Self-reference for nested replies (NULL = top-level comment).
    parent_comment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comments.id"), index=True, nullable=True,
    )
