"""Projects router (backend-requirements mục 2).

Read: any authenticated user — an INTERN only sees the projects they lead or
belong to. Write: MENTOR/ADMIN.
"""
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
from app.models.enums import Department
from app.models.project import ProjectStatus
from app.schemas.common import Page
from app.schemas.project import (
    AddProjectMembersRequest,
    ProjectCreate,
    ProjectDetailOut,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services import project_service as svc

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
    search: Annotated[str | None, Query(description="search in title or code")] = None,
    department: Annotated[Department | None, Query()] = None,
    status_: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    member_id: Annotated[
        int | None, Query(description="only projects this user belongs to")
    ] = None,
) -> Page[ProjectOut]:
    """An INTERN always gets only their own projects, whatever the filters."""
    stmt = svc.list_query(
        viewer=current_user, search=search, department=department,
        status_=status_, member_id=member_id,
    )
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    projects = list(rows)
    counts = svc.member_counts(db, [p.id for p in projects])
    leads = svc.lead_names(db, projects)
    return Page(
        items=[
            svc.to_out(
                p, member_count=counts.get(p.id, 0), lead_name=leads.get(p.lead_user_id),
            )
            for p in projects
        ],
        total=total, page=page, size=size, pages=pages,
    )


@router.post("", response_model=ProjectDetailOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, db: DbSession, current_user: MentorRequired,
) -> ProjectDetailOut:
    """MENTOR/ADMIN. 409 if `code` already exists."""
    return svc.to_detail(db, svc.create_project(db, payload))


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(
    project_id: int, db: DbSession, current_user: CurrentUser,
) -> ProjectDetailOut:
    """403 for an intern who is neither the lead nor a member."""
    p = svc.get_project(db, project_id)
    svc.ensure_can_view(db, p, current_user)
    return svc.to_detail(db, p)


@router.patch("/{project_id}", response_model=ProjectDetailOut)
def update_project(
    project_id: int, payload: ProjectUpdate, db: DbSession, current_user: MentorRequired,
) -> ProjectDetailOut:
    p = svc.update_project(db, svc.get_project(db, project_id), payload)
    return svc.to_detail(db, p)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession, current_user: MentorRequired) -> None:
    """Soft delete (sets deleted_at); tasks keep referencing the project."""
    svc.soft_delete(db, svc.get_project(db, project_id))


@router.post("/{project_id}/members", response_model=list[ProjectMemberOut])
def add_members(
    project_id: int,
    payload: AddProjectMembersRequest,
    db: DbSession,
    current_user: MentorRequired,
) -> list[ProjectMemberOut]:
    """Bulk add (one transaction). Skips duplicates / unknown ids.
    Returns the project's current member list."""
    members = svc.add_members(db, project_id, payload.user_ids)
    return [ProjectMemberOut.model_validate(m) for m in members]


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    project_id: int, user_id: int, db: DbSession, current_user: MentorRequired,
) -> None:
    svc.remove_member(db, project_id, user_id)
