"""Documents, Tags, and the document<->tag join table."""
import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class DocumentType(str, enum.Enum):
    VIDEO = "VIDEO"
    PDF = "PDF"
    LINK = "LINK"
    ARTICLE = "ARTICLE"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Soft delete (mục 6 CLAUDE.md — xóa document là soft delete).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Many-to-many via the document_tags join table (ORM only, no schema change).
    tags: Mapped[list["Tag"]] = relationship(
        secondary="document_tags", lazy="selectin", order_by="Tag.name",
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)


class DocumentTag(Base):
    """N-N join; composite PK (document_id, tag_id)."""
    __tablename__ = "document_tags"

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id"), primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tags.id"), primary_key=True,
    )
