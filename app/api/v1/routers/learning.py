"""Learning & progress router (API_SPEC mục 8).

Các endpoint `/me/...` chỉ làm việc trên lượt gán CỦA CHÍNH người gọi (service kiểm
tra sở hữu -> 403 nếu không phải).

Hai endpoint `/users/{user_id}/roadmaps...` là bản dành cho MENTOR/ADMIN xem tiến độ
học của một Thực tập sinh (dùng ở màn hồ sơ chi tiết). Chúng gọi CÙNG service với
`/me/...`, chỉ khác là truyền user đích thay vì người gọi — nên luật "assignment phải
thuộc đúng người đó" vẫn được giữ, không lộ dữ liệu của người khác.
"""
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.schemas.learning import (
    CompleteRequest,
    CompleteResponse,
    MyRoadmapDetail,
    MyRoadmapItem,
)
from app.services import learning_service as svc
from app.services import user_service

router = APIRouter(tags=["learning"])


@router.get("/me/roadmaps", response_model=list[MyRoadmapItem])
def my_roadmaps(db: DbSession, current_user: CurrentUser) -> list[MyRoadmapItem]:
    return svc.list_my_roadmaps(db, current_user)


@router.get("/me/roadmaps/{assignment_id}", response_model=MyRoadmapDetail)
def my_roadmap_detail(
    assignment_id: int, db: DbSession, current_user: CurrentUser,
) -> MyRoadmapDetail:
    return svc.get_my_roadmap_detail(db, current_user, assignment_id)


@router.get("/users/{user_id}/roadmaps", response_model=list[MyRoadmapItem])
def user_roadmaps(
    user_id: int, db: DbSession, current_user: MentorRequired,
) -> list[MyRoadmapItem]:
    """MENTOR/ADMIN. Các lộ trình đã gán cho một người + % tiến độ từng lộ trình.

    404 nếu user không tồn tại. Dùng ở màn hồ sơ chi tiết Thực tập sinh.
    """
    return svc.list_my_roadmaps(db, user_service.get_user(db, user_id))


@router.get(
    "/users/{user_id}/roadmaps/{assignment_id}", response_model=MyRoadmapDetail,
)
def user_roadmap_detail(
    user_id: int, assignment_id: int, db: DbSession, current_user: MentorRequired,
) -> MyRoadmapDetail:
    """MENTOR/ADMIN. Chi tiết một lộ trình của người đó: từng chặng, từng bài học và
    bài nào đã hoàn thành.

    403 nếu `assignment_id` không thuộc `user_id` (service kiểm tra sở hữu), 404 nếu
    user hoặc lượt gán không tồn tại.
    """
    return svc.get_my_roadmap_detail(
        db, user_service.get_user(db, user_id), assignment_id,
    )


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
