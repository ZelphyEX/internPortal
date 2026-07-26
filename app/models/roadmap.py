"""Roadmap -> Module (Chặng) -> ModuleDocument (Bài học)."""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import CreatedAtMixin, TimestampMixin
from app.models.enums import DEPARTMENT_ENUM, Department


class Roadmap(TimestampMixin, Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    modules: Mapped[list["Module"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="Module.position, Module.id",
    )


class Module(TimestampMixin, Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roadmaps.id"), index=True, nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ordering position within the roadmap.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Course metadata the frontend shows on the module/course card
    # (docs/backend-requirements.md mục 5).
    track: Mapped[Department | None] = mapped_column(DEPARTMENT_ENUM, nullable=True)
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Free text, e.g. "2 tuần" / "8 giờ" — display only, not parsed.
    duration_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # List of skill names; replaced wholesale on update.
    key_skills: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"),
    )

    roadmap: Mapped["Roadmap"] = relationship(back_populates="modules")
    module_documents: Mapped[list["ModuleDocument"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="ModuleDocument.position, ModuleDocument.id",
    )


class ModuleDocument(CreatedAtMixin, Base):
    """A document assigned into a module. `id` == module_document_id
    (referenced by lesson_progress and comments)."""
    __tablename__ = "module_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("modules.id"), index=True, nullable=False,
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id"), index=True, nullable=False,
    )
    # Ordering position within the module.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    module: Mapped["Module"] = relationship(back_populates="module_documents")
    document: Mapped["Document"] = relationship()  # noqa: F821  (app.models.document.Document)
