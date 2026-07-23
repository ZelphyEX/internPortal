"""Roadmap-assignment router (API_SPEC mục 7). MENTOR/ADMIN only."""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, MentorRequired
from app.core.pagination import DEFAULT_PAGE, DEFAULT_SIZE, MAX_SIZE, paginate
from app.models.assignment import AssignmentStatus
from app.schemas.assignment import (
    AssignGroupRequest,
    AssignGroupResponse,
    AssignmentListItem,
    AssignRequest,
    AssignResponse,
)
from app.schemas.common import Page
from app.services import assignment_service as svc

router = APIRouter(tags=["assignments"])


@router.post(
    "/roadmaps/{roadmap_id}/assign",
    response_model=AssignResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_roadmap(
    roadmap_id: int, payload: AssignRequest, db: DbSession, current_user: MentorRequired,
) -> AssignResponse:
    """Assign a roadmap to one/many interns. Already-assigned interns are skipped."""
    return svc.assign(db, roadmap_id, payload.user_ids)


@router.post(
    "/roadmaps/{roadmap_id}/assign-group",
    response_model=AssignGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_roadmap_to_group(
    roadmap_id: int, payload: AssignGroupRequest, db: DbSession, current_user: MentorRequired,
) -> AssignGroupResponse:
    """Bulk-assign a roadmap to every intern in a group (one transaction)."""
    assigned, skipped = svc.assign_group(db, roadmap_id, payload.group_id)
    return AssignGroupResponse(
        group_id=payload.group_id, assigned_count=assigned, skipped_existing=skipped,
    )


@router.delete("/roadmap-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int, db: DbSession, current_user: MentorRequired,
) -> None:
    svc.delete_assignment(db, svc.get_assignment(db, assignment_id))


@router.get("/roadmap-assignments", response_model=Page[AssignmentListItem])
def list_assignments(
    db: DbSession,
    current_user: MentorRequired,
    page: Annotated[int, Query(ge=1)] = DEFAULT_PAGE,
    size: Annotated[int, Query(ge=1, le=MAX_SIZE)] = DEFAULT_SIZE,
    roadmap_id: Annotated[int | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
    group_id: Annotated[int | None, Query()] = None,
    status_: Annotated[AssignmentStatus | None, Query(alias="status")] = None,
) -> Page[AssignmentListItem]:
    stmt = svc.list_query(
        roadmap_id=roadmap_id, user_id=user_id, group_id=group_id, status_=status_,
    )
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(
        items=svc.to_list_items(db, list(rows)),
        total=total, page=page, size=size, pages=pages,
    )
