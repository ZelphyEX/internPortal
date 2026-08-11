"""Điểm thi thử Anthropic Mock Exam.

  * Người dùng : nộp kết quả, xem điểm của chính mình.
  * MENTOR/ADMIN: xem điểm của từng Thực tập sinh + trung bình toàn bộ.

Cách tính điểm (thang 100..1000, đỗ >= 720) nằm ở `app.services.exam_service`.
"""
from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, MentorRequired
from app.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    PageQuery,
    SizeQuery,
    paginate,
)
from app.schemas.common import Page
from app.schemas.exam import (
    ExamAttemptCreate,
    ExamAttemptOut,
    ExamOverview,
    ExamSummary,
)
from app.services import exam_service as svc
from app.services import user_service

router = APIRouter(tags=["exams"])


# --------------------------------------------------------------------------- #
# Của chính mình
# --------------------------------------------------------------------------- #
@router.post(
    "/exam-attempts", response_model=ExamAttemptOut, status_code=status.HTTP_201_CREATED,
)
def submit_attempt(
    payload: ExamAttemptCreate, db: DbSession, current_user: CurrentUser,
) -> ExamAttemptOut:
    """Nộp kết quả một lần thi ở **chế độ thi** (không nộp bài luyện tập).

    Điểm do server tính từ `correct_count`/`total_questions` theo thang 100..1000;
    client không gửi `score` lên. 400 nếu `correct_count > total_questions`.
    """
    return svc.record_attempt(db, current_user, payload)


@router.get("/exam-attempts/me", response_model=Page[ExamAttemptOut])
def list_my_attempts(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
) -> Page[ExamAttemptOut]:
    """Lịch sử làm bài của chính mình, mới nhất trước."""
    rows, total, pages = paginate(
        db, svc.attempts_query(current_user.id), page=page, size=size,
    )
    return Page(items=list(rows), total=total, page=page, size=size, pages=pages)


@router.get("/exam-attempts/me/summary", response_model=ExamSummary)
def my_summary(db: DbSession, current_user: CurrentUser) -> ExamSummary:
    """Điểm trung bình + điểm tốt nhất từng đề của chính mình.

    `avg_score` = trung bình điểm TỐT NHẤT của mỗi đề đã thi; `null` nếu chưa thi
    bài nào ở chế độ thi.
    """
    return svc.summary_for(db, current_user)


# --------------------------------------------------------------------------- #
# Mentor/Admin xem của người khác
# --------------------------------------------------------------------------- #
@router.get("/exam-attempts/overview", response_model=ExamOverview)
def exam_overview(db: DbSession, current_user: MentorRequired) -> ExamOverview:
    """MENTOR/ADMIN. Điểm trung bình toàn bộ Thực tập sinh + bảng điểm từng người.

    Dùng cho thẻ "Điểm Năng lực TB" ở Dashboard của Mentor.
    """
    return svc.overview(db, current_user)


@router.get("/users/{user_id}/exam-attempts", response_model=Page[ExamAttemptOut])
def list_user_attempts(
    user_id: int,
    db: DbSession,
    current_user: MentorRequired,
    page: PageQuery = DEFAULT_PAGE,
    size: SizeQuery = DEFAULT_SIZE,
) -> Page[ExamAttemptOut]:
    """MENTOR/ADMIN. Lịch sử làm bài của một người. 404 nếu không tồn tại."""
    target = user_service.get_user(db, user_id)
    
    if current_user.id != target.id:
        from app.models.user import Role
        from fastapi import HTTPException, status
        if current_user.role == Role.MENTOR and target.role != Role.INTERN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mentor chỉ có quyền truy cập kết quả thi của Thực tập sinh."
            )
        if current_user.role == Role.ADMIN and target.role not in (Role.MENTOR, Role.INTERN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin chỉ có quyền truy cập kết quả thi của Mentor và Thực tập sinh."
            )

    rows, total, pages = paginate(db, svc.attempts_query(target.id), page=page, size=size)
    return Page(items=list(rows), total=total, page=page, size=size, pages=pages)


@router.get("/users/{user_id}/exam-attempts/summary", response_model=ExamSummary)
def user_summary(
    user_id: int, db: DbSession, current_user: MentorRequired,
) -> ExamSummary:
    """MENTOR/ADMIN. Điểm trung bình + điểm từng đề của một người."""
    target = user_service.get_user(db, user_id)
    
    if current_user.id != target.id:
        from app.models.user import Role
        from fastapi import HTTPException, status
        if current_user.role == Role.MENTOR and target.role != Role.INTERN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mentor chỉ có quyền truy cập kết quả thi của Thực tập sinh."
            )
        if current_user.role == Role.ADMIN and target.role not in (Role.MENTOR, Role.INTERN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin chỉ có quyền truy cập kết quả thi của Mentor và Thực tập sinh."
            )

    return svc.summary_for(db, target)
