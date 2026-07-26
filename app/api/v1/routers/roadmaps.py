"""Roadmaps / Modules / module-documents router (API_SPEC mục 6)."""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.schemas.common import Page
from app.schemas.roadmap import (
    AssignDocsRequest,
    ModuleCreate,
    ModuleDocumentOut,
    ModuleOut,
    ModuleUpdate,
    RoadmapCreate,
    RoadmapDetailOut,
    RoadmapOut,
    RoadmapUpdate,
)
from app.services import roadmap_service as svc

router = APIRouter(tags=["roadmaps"])


# ---------- Roadmaps ----------
@router.get("/roadmaps", response_model=Page[RoadmapOut])
def list_roadmaps(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in title")] = None,
) -> Page[RoadmapOut]:
    rows, total, pages = paginate(db, svc.list_query(search=search), page=page, size=size)
    counts = svc.module_counts(db, [r.id for r in rows])
    return Page(
        items=[svc.to_roadmap_out(r, counts.get(r.id, 0)) for r in rows],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("/roadmaps", response_model=RoadmapOut, status_code=status.HTTP_201_CREATED)
def create_roadmap(payload: RoadmapCreate, db: DbSession, current_user: MentorRequired) -> RoadmapOut:
    r = svc.create_roadmap(db, payload)
    return svc.to_roadmap_out(r, 0)


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapDetailOut)
def get_roadmap(roadmap_id: int, db: DbSession, current_user: CurrentUser) -> RoadmapDetailOut:
    return svc.get_roadmap_detail(db, roadmap_id)


@router.patch("/roadmaps/{roadmap_id}", response_model=RoadmapOut)
def update_roadmap(
    roadmap_id: int, payload: RoadmapUpdate, db: DbSession, current_user: MentorRequired,
) -> RoadmapOut:
    r = svc.update_roadmap(db, svc.get_roadmap(db, roadmap_id), payload)
    counts = svc.module_counts(db, [r.id])
    return svc.to_roadmap_out(r, counts.get(r.id, 0))


@router.delete("/roadmaps/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_roadmap(roadmap_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_roadmap(db, svc.get_roadmap(db, roadmap_id))


# ---------- Modules ----------
@router.post(
    "/roadmaps/{roadmap_id}/modules",
    response_model=ModuleOut,
    status_code=status.HTTP_201_CREATED,
)
def add_module(
    roadmap_id: int, payload: ModuleCreate, db: DbSession, current_user: MentorRequired,
) -> ModuleOut:
    return svc.add_module(db, roadmap_id, payload)


@router.patch("/modules/{module_id}", response_model=ModuleOut)
def update_module(
    module_id: int, payload: ModuleUpdate, db: DbSession, current_user: MentorRequired,
) -> ModuleOut:
    return svc.update_module(db, svc.get_module(db, module_id), payload)


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(module_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_module(db, svc.get_module(db, module_id))


# ---------- module-documents (assign / remove) ----------
@router.post(
    "/modules/{module_id}/documents",
    response_model=list[ModuleDocumentOut],
    status_code=status.HTTP_201_CREATED,
)
def assign_documents(
    module_id: int, payload: AssignDocsRequest, db: DbSession, current_user: MentorRequired,
) -> list[ModuleDocumentOut]:
    return svc.assign_documents(db, module_id, payload.items)


@router.delete("/module-documents/{module_document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_module_document(
    module_document_id: int, db: DbSession, current_user: MentorRequired,
) -> None:
    """Remove a document from a module (link only; keeps the document)."""
    svc.delete_module_document(db, svc.get_module_document(db, module_document_id))
