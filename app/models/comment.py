"""Comments on a lesson (module_document), with self-referential replies."""
from sqlalchemy import BigInteger, ForeignKey, Text
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
    # Self-reference for nested replies (NULL = top-level comment).
    parent_comment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comments.id"), index=True, nullable=True,
    )
