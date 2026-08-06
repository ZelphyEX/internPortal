"""Roadmap -> Module (Chặng) -> ModuleDocument (Bài học) -> LessonAttachment (tài liệu).

Ghi chú mô hình bài học:
  * Bài học CHÍNH LÀ một dòng `module_documents` — `id` của nó là `module_document_id`
    mà `lesson_progress` và `comments` đang tham chiếu, nên không đổi khoá này.
  * Bài học tự mang `title` + `content_url` (tên hiển thị và link video/bài giảng).
    `document_id` để NULL được: bài học tạo tay không sinh rác trong Thư viện Tài liệu.
    Nếu bài học được tạo từ một tài liệu có sẵn thì `document_id` trỏ tới tài liệu đó
    và tên/link lấy theo tài liệu khi hai cột kia bỏ trống.
  * Tài liệu đính kèm hiển thị NGAY DƯỚI bài học nằm ở bảng `lesson_attachments`.
"""
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, Text, UniqueConstraint, text
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
    # Hạn hoàn thành chặng học do Mentor đặt. Frontend hiển thị "còn N ngày".
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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
    """Một BÀI HỌC trong chặng. `id` == module_document_id
    (được lesson_progress và comments tham chiếu — không đổi)."""
    __tablename__ = "module_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("modules.id"), index=True, nullable=False,
    )
    # NULL khi bài học được tạo tay (chỉ có tên + link), không lấy từ Thư viện.
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("documents.id"), index=True, nullable=True,
    )
    # Tên và link riêng của bài học. Bỏ trống thì lấy theo `document`.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ordering position within the module.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    module: Mapped["Module"] = relationship(back_populates="module_documents")
    document: Mapped["Document"] = relationship()  # noqa: F821  (app.models.document.Document)
    attachments: Mapped[list["LessonAttachment"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonAttachment.position, LessonAttachment.id",
    )

    @property
    def display_title(self) -> str:
        """Tên hiển thị: ưu tiên tên riêng của bài học, không có thì lấy của tài liệu."""
        if self.title:
            return self.title
        return self.document.title if self.document is not None else "(chưa đặt tên)"

    @property
    def display_url(self) -> str | None:
        """Link mở khi bấm vào tên bài học."""
        if self.content_url:
            return self.content_url
        return self.document.content_url if self.document is not None else None


class LessonAttachment(CreatedAtMixin, Base):
    """Tài liệu đính kèm hiển thị ngay dưới một bài học."""
    __tablename__ = "lesson_attachments"
    __table_args__ = (
        UniqueConstraint("module_document_id", "document_id", name="uq_lesson_attachment"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("module_documents.id"), index=True, nullable=False,
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id"), index=True, nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lesson: Mapped["ModuleDocument"] = relationship(back_populates="attachments")
    document: Mapped["Document"] = relationship()  # noqa: F821
