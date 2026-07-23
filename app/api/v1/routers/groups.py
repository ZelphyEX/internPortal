"""Groups router (API_SPEC mục 4). MENTOR/ADMIN only."""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, MentorRequired
from app.core.pagination import DEFAULT_PAGE, DEFAULT_SIZE, MAX_SIZE, paginate
from app.schemas.common import Page
from app.schemas.group import (
    AddMembersRequest,
    GroupCreate,
    GroupDetailOut,
    GroupMemberOut,
    GroupOut,
    GroupUpdate,
)
from app.services import group_service as svc

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=Page[GroupOut])
def list_groups(
    db: DbSession,
    current_user: MentorRequired,
    page: Annotated[int, Query(ge=1)] = DEFAULT_PAGE,
    size: Annotated[int, Query(ge=1, le=MAX_SIZE)] = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in name")] = None,
    cohort: Annotated[str | None, Query()] = None,
) -> Page[GroupOut]:
    stmt = svc.list_query(search=search, cohort=cohort)
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    counts = svc.member_counts(db, [g.id for g in rows])
    return Page(
        items=[svc.to_group_out(g, counts.get(g.id, 0)) for g in rows],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: DbSession, current_user: MentorRequired) -> GroupOut:
    g = svc.create_group(db, payload)
    return svc.to_group_out(g, 0)


@router.get("/{group_id}", response_model=GroupDetailOut)
def get_group(group_id: int, db: DbSession, current_user: MentorRequired) -> GroupDetailOut:
    g = svc.get_group(db, group_id)
    members = svc.list_members(db, group_id)
    return GroupDetailOut(
        id=g.id, name=g.name, cohort=g.cohort, description=g.description,
        members=[GroupMemberOut.model_validate(m) for m in members],
    )


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int, payload: GroupUpdate, db: DbSession, current_user: MentorRequired,
) -> GroupOut:
    g = svc.update_group(db, svc.get_group(db, group_id), payload)
    counts = svc.member_counts(db, [g.id])
    return svc.to_group_out(g, counts.get(g.id, 0))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, db: DbSession, current_user: MentorRequired) -> None:
    svc.delete_group(db, svc.get_group(db, group_id))


@router.post("/{group_id}/members", response_model=list[GroupMemberOut])
def add_members(
    group_id: int, payload: AddMembersRequest, db: DbSession, current_user: MentorRequired,
) -> list[GroupMemberOut]:
    """Add many interns (bulk, one transaction). Skips duplicates / unknown ids.
    Returns the group's current member list."""
    members = svc.add_members(db, group_id, payload.user_ids)
    return [GroupMemberOut.model_validate(m) for m in members]


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: int, user_id: int, db: DbSession, current_user: MentorRequired,
) -> None:
    svc.remove_member(db, group_id, user_id)
