"""Roadmap / Module / module-document business logic."""
from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.document import Document
from app.models.roadmap import Module, ModuleDocument, Roadmap
from app.schemas.roadmap import (
    AssignDocItem,
    LessonInModule,
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
            .selectinload(ModuleDocument.document)
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
                documents=[
                    LessonInModule(
                        module_document_id=md.id,
                        document_id=md.document_id,
                        title=md.document.title,
                        type=md.document.type,
                        position=md.position,
                    )
                    for md in m.module_documents
                ],
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
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def update_module(db: Session, m: Module, data: ModuleUpdate) -> Module:
    for key, value in data.model_dump(exclude_unset=True).items():
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
    return [
        ModuleDocumentOut(
            module_document_id=md.id,
            module_id=md.module_id,
            document_id=md.document_id,
            position=md.position,
        )
        for md in created
    ]


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
