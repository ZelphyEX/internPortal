"""Roadmap -> Module (Chặng) -> ModuleDocument (Bài học)."""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import CreatedAtMixin, TimestampMixin


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
