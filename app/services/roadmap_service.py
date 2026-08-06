"""Roadmap / Module / module-document business logic."""
from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.document import Document
from app.models.roadmap import LessonAttachment, Module, ModuleDocument, Roadmap
from app.schemas.roadmap import (
    AssignDocItem,
    LessonAttachmentOut,
    LessonCreate,
    LessonInModule,
    LessonUpdate,
    ModuleCreate,
    ModuleDocumentOut,
    ModuleUpdate,
    ModuleWithDocs,
    RoadmapCreate,
    RoadmapDetailOut,
    RoadmapOut,
    RoadmapUpdate,
)

_IN_USE = "Resource is in use (assignments/progress/comments reference it)"


def to_attachment_out(a: LessonAttachment) -> LessonAttachmentOut:
    return LessonAttachmentOut(
        attachment_id=a.id,
        document_id=a.document_id,
        title=a.document.title,
        type=a.document.type,
        content_url=a.document.content_url,
        position=a.position,
    )


def to_lesson_out(md: ModuleDocument) -> LessonInModule:
    """Bài học + tài liệu đính kèm. Tên/link ưu tiên của bài học, thiếu thì lấy
    từ tài liệu gốc (bài học tạo từ Thư viện Tài liệu)."""
    return LessonInModule(
        module_document_id=md.id,
        document_id=md.document_id,
        title=md.display_title,
        content_url=md.display_url,
        type=md.document.type if md.document is not None else None,
        position=md.position,
        attachments=[to_attachment_out(a) for a in md.attachments],
    )


def to_module_document_out(md: ModuleDocument) -> ModuleDocumentOut:
    return ModuleDocumentOut(
        module_document_id=md.id,
        module_id=md.module_id,
        document_id=md.document_id,
        title=md.display_title,
        content_url=md.display_url,
        position=md.position,
    )


# ---------- Roadmap ----------
def list_query(*, search: str | None) -> Select:
    stmt = select(Roadmap)
    if search:
        stmt = stmt.where(Roadmap.title.ilike(f"%{search}%"))
    return stmt.order_by(Roadmap.id.desc())


def module_counts(db: Session, roadmap_ids: list[int]) -> dict[int, int]:
    if not roadmap_ids:
        return {}
    rows = db.execute(
        select(Module.roadmap_id, func.count())
        .where(Module.roadmap_id.in_(roadmap_ids))
        .group_by(Module.roadmap_id)
    ).all()
    return {rid: cnt for rid, cnt in rows}


def to_roadmap_out(r: Roadmap, count: int) -> RoadmapOut:
    return RoadmapOut(id=r.id, title=r.title, description=r.description, module_count=count)


def get_roadmap(db: Session, roadmap_id: int) -> Roadmap:
    r = db.get(Roadmap, roadmap_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    return r


def create_roadmap(db: Session, data: RoadmapCreate) -> Roadmap:
    r = Roadmap(title=data.title, description=data.description)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def update_roadmap(db: Session, r: Roadmap, data: RoadmapUpdate) -> Roadmap:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(r, key, value)
    db.commit()
    db.refresh(r)
    return r


def delete_roadmap(db: Session, r: Roadmap) -> None:
    # cascade deletes modules + module_documents; 409 if external refs exist.
    try:
        db.delete(r)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_IN_USE)


def get_roadmap_detail(db: Session, roadmap_id: int) -> RoadmapDetailOut:
    r = db.scalar(
        select(Roadmap)
        .where(Roadmap.id == roadmap_id)
        .options(
            selectinload(Roadmap.modules)
            .selectinload(Module.module_documents)
            .selectinload(ModuleDocument.document),
            selectinload(Roadmap.modules)
            .selectinload(Module.module_documents)
            .selectinload(ModuleDocument.attachments)
            .selectinload(LessonAttachment.document),
        )
    )
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roadmap not found")
    return RoadmapDetailOut(
        id=r.id,
        title=r.title,
        description=r.description,
        modules=[
            ModuleWithDocs(
                id=m.id,
                title=m.title,
                description=m.description,
                position=m.position,
                track=m.track,
                week_number=m.week_number,
                duration_text=m.duration_text,
                key_skills=m.key_skills or [],
                start_date=m.start_date,
                end_date=m.end_date,
                documents=[to_lesson_out(md) for md in m.module_documents],
            )
            for m in r.modules
        ],
    )


# ---------- Module ----------
def get_module(db: Session, module_id: int) -> Module:
    m = db.get(Module, module_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return m


def add_module(db: Session, roadmap_id: int, data: ModuleCreate) -> Module:
    get_roadmap(db, roadmap_id)  # 404 if roadmap missing
    m = Module(
        roadmap_id=roadmap_id,
        title=data.title,
        description=data.description,
        position=data.position,
        track=data.track,
        week_number=data.week_number,
        duration_text=data.duration_text,
        key_skills=data.key_skills,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def update_module(db: Session, m: Module, data: ModuleUpdate) -> Module:
    fields = data.model_dump(exclude_unset=True)
    if "key_skills" in fields and fields["key_skills"] is None:
        fields["key_skills"] = []  # the column is NOT NULL
    for key, value in fields.items():
        setattr(m, key, value)
    db.commit()
    db.refresh(m)
    return m


def delete_module(db: Session, m: Module) -> None:
    try:
        db.delete(m)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_IN_USE)


# ---------- module-documents ----------
def assign_documents(
    db: Session, module_id: int, items: list[AssignDocItem],
) -> list[ModuleDocumentOut]:
    get_module(db, module_id)  # 404 if module missing
    doc_ids = [it.document_id for it in items]
    existing = set(
        db.scalars(
            select(Document.id).where(
                Document.id.in_(doc_ids), Document.deleted_at.is_(None)
            )
        ).all()
    )
    missing = set(doc_ids) - existing
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown document_ids: {sorted(missing)}",
        )
    created = [
        ModuleDocument(module_id=module_id, document_id=it.document_id, position=it.position)
        for it in items
    ]
    db.add_all(created)
    db.commit()
    for md in created:
        db.refresh(md)
    return [to_module_document_out(md) for md in created]


# ---------- Bài học tạo tay (tên + link) ----------
def create_lesson(db: Session, module_id: int, data: LessonCreate) -> ModuleDocumentOut:
    """Tạo bài học bằng tên + link, KHÔNG sinh bản ghi trong Thư viện Tài liệu."""
    get_module(db, module_id)  # 404 nếu chặng không tồn tại
    md = ModuleDocument(
        module_id=module_id,
        document_id=None,
        title=data.title,
        content_url=data.content_url,
        position=data.position,
    )
    db.add(md)
    db.commit()
    db.refresh(md)
    return to_module_document_out(md)


def update_lesson(db: Session, md: ModuleDocument, data: LessonUpdate) -> ModuleDocumentOut:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(md, key, value)
    db.commit()
    db.refresh(md)
    return to_module_document_out(md)


# ---------- Tài liệu đính kèm dưới bài học ----------
def attach_documents(
    db: Session, md: ModuleDocument, document_ids: list[int],
) -> list[LessonAttachmentOut]:
    """Đính tài liệu vào bài học. Bỏ qua tài liệu đã đính (không báo lỗi)."""
    existing_docs = set(
        db.scalars(
            select(Document.id).where(
                Document.id.in_(document_ids), Document.deleted_at.is_(None)
            )
        ).all()
    )
    missing = set(document_ids) - existing_docs
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown document_ids: {sorted(missing)}",
        )
    already = set(
        db.scalars(
            select(LessonAttachment.document_id).where(
                LessonAttachment.module_document_id == md.id
            )
        ).all()
    )
    start_pos = len(already)
    for offset, doc_id in enumerate(d for d in document_ids if d not in already):
        db.add(
            LessonAttachment(
                module_document_id=md.id, document_id=doc_id, position=start_pos + offset,
            )
        )
    db.commit()
    rows = db.scalars(
        select(LessonAttachment)
        .where(LessonAttachment.module_document_id == md.id)
        .options(selectinload(LessonAttachment.document))
        .order_by(LessonAttachment.position, LessonAttachment.id)
    ).all()
    return [to_attachment_out(a) for a in rows]


def detach_document(db: Session, module_document_id: int, document_id: int) -> None:
    """Gỡ tài liệu khỏi bài học (không xoá tài liệu gốc). Idempotent."""
    a = db.scalar(
        select(LessonAttachment).where(
            LessonAttachment.module_document_id == module_document_id,
            LessonAttachment.document_id == document_id,
        )
    )
    if a is not None:
        db.delete(a)
        db.commit()


def get_module_document(db: Session, module_document_id: int) -> ModuleDocument:
    md = db.get(ModuleDocument, module_document_id)
    if md is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="module_document not found"
        )
    return md


def delete_module_document(db: Session, md: ModuleDocument) -> None:
    """Removes the link only (not the underlying document). 409 if in use."""
    try:
        db.delete(md)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_IN_USE)
