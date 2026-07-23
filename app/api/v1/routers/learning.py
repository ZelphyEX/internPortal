"""Learning & progress router (API_SPEC mục 8).

All endpoints operate on the CALLER's own assignments only (ownership checked
in the service -> 403 otherwise).
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.learning import (
    CompleteRequest,
    CompleteResponse,
    MyRoadmapDetail,
    MyRoadmapItem,
)
from app.services import learning_service as svc

router = APIRouter(tags=["learning"])


@router.get("/me/roadmaps", response_model=list[MyRoadmapItem])
def my_roadmaps(db: DbSession, current_user: CurrentUser) -> list[MyRoadmapItem]:
    return svc.list_my_roadmaps(db, current_user)


@router.get("/me/roadmaps/{assignment_id}", response_model=MyRoadmapDetail)
def my_roadmap_detail(
    assignment_id: int, db: DbSession, current_user: CurrentUser,
) -> MyRoadmapDetail:
    return svc.get_my_roadmap_detail(db, current_user, assignment_id)


@router.post(
    "/lessons/{module_document_id}/complete",
    response_model=CompleteResponse,
    status_code=status.HTTP_200_OK,
)
def mark_complete(
    module_document_id: int, payload: CompleteRequest, db: DbSession, current_user: CurrentUser,
) -> CompleteResponse:
    return svc.set_completion(
        db, current_user, module_document_id, payload.assignment_id, completed=True,
    )


@router.delete("/lessons/{module_document_id}/complete", response_model=CompleteResponse)
def unmark_complete(
    module_document_id: int,
    db: DbSession,
    current_user: CurrentUser,
    assignment_id: Annotated[int, Query()],
) -> CompleteResponse:
    return svc.set_completion(
        db, current_user, module_document_id, assignment_id, completed=False,
    )
