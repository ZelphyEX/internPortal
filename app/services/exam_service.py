"""Nghiệp vụ điểm thi thử Anthropic Mock Exam.

CÁCH TÍNH ĐIỂM (một nơi duy nhất — mọi chỗ khác gọi vào đây):

  * Thang điểm chuẩn hoá: **100 .. 1000**.
  * Điểm đỗ: **>= 720** (~72%).
  * Đề gồm 60 câu trắc nghiệm (một hoặc nhiều đáp án), làm trong 120 phút.
  * Câu trả lời đúng phải khớp CHÍNH XÁC tập đáp án đúng (client chấm, xem
    `MockExamView.handleSubmitExam`).

LƯU Ý VỀ TRỌNG SỐ: đặc tả nói điểm tính theo "độ khó và trọng số từng câu", nhưng dữ
liệu đề hiện tại (`src/data/CF.tests/**.json`) KHÔNG có trường độ khó/trọng số nào —
mọi câu đang được tính như nhau. Khi đề có thêm trường đó, chỉ cần sửa
`scaled_score()` nhận thêm tổng trọng số đạt được / tổng trọng số tối đa; phần còn
lại của hệ thống không phải đổi.
"""
from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.exam_attempt import ExamAttempt
from app.models.user import Role, User
from app.schemas.exam import (
    ExamAttemptCreate,
    ExamBest,
    ExamOverview,
    ExamSummary,
)

#: Thang điểm chuẩn hoá.
SCALE_MIN = 100
SCALE_MAX = 1000
#: Điểm tối thiểu để đỗ.
PASSING_SCORE = 720


def scaled_score(correct_count: int, total_questions: int) -> int:
    """Quy đổi số câu đúng sang thang 100..1000.

    0 câu đúng -> 100 (không phải 0: thang bắt đầu từ 100), đúng hết -> 1000.
    """
    if total_questions <= 0:
        return SCALE_MIN
    ratio = min(1.0, max(0.0, correct_count / total_questions))
    return round(SCALE_MIN + ratio * (SCALE_MAX - SCALE_MIN))


def is_passing(score: int) -> bool:
    return score >= PASSING_SCORE


# --------------------------------------------------------------------------- #
# Ghi kết quả
# --------------------------------------------------------------------------- #
def record_attempt(db: Session, user: User, data: ExamAttemptCreate) -> ExamAttempt:
    """Lưu một lần thi. 400 nếu số câu đúng lớn hơn tổng số câu."""
    if data.correct_count > data.total_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số câu đúng không thể lớn hơn tổng số câu.",
        )
    score = scaled_score(data.correct_count, data.total_questions)
    attempt = ExamAttempt(
        user_id=user.id,
        exam_id=data.exam_id,
        exam_title=data.exam_title,
        exam_code=data.exam_code,
        total_questions=data.total_questions,
        correct_count=data.correct_count,
        score=score,
        passed=is_passing(score),
        duration_seconds=data.duration_seconds,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


# --------------------------------------------------------------------------- #
# Đọc kết quả
# --------------------------------------------------------------------------- #
def attempts_query(user_id: int) -> Select:
    """Lịch sử làm bài của một người, mới nhất trước."""
    return (
        select(ExamAttempt)
        .where(ExamAttempt.user_id == user_id)
        .order_by(ExamAttempt.created_at.desc(), ExamAttempt.id.desc())
    )


def _best_rows(db: Session, user_ids: list[int]) -> dict[int, list[ExamBest]]:
    """Điểm tốt nhất theo từng đề, gom theo user. Một truy vấn cho nhiều người."""
    if not user_ids:
        return {}
    stmt = (
        select(
            ExamAttempt.user_id,
            ExamAttempt.exam_id,
            func.max(ExamAttempt.exam_title).label("exam_title"),
            func.max(ExamAttempt.exam_code).label("exam_code"),
            func.max(ExamAttempt.score).label("best_score"),
            func.count(ExamAttempt.id).label("attempts"),
            func.max(ExamAttempt.created_at).label("last_taken_at"),
        )
        .where(ExamAttempt.user_id.in_(user_ids))
        .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
        .order_by(func.max(ExamAttempt.score).desc())
    )
    grouped: dict[int, list[ExamBest]] = {}
    for row in db.execute(stmt).all():
        grouped.setdefault(row.user_id, []).append(
            ExamBest(
                exam_id=row.exam_id,
                exam_title=row.exam_title,
                exam_code=row.exam_code,
                best_score=row.best_score,
                passed=is_passing(row.best_score),
                attempts=row.attempts,
                last_taken_at=row.last_taken_at,
            )
        )
    return grouped


def _summary_from_bests(user: User, bests: list[ExamBest]) -> ExamSummary:
    summary = ExamSummary(
        user_id=user.id, full_name=user.full_name, email=user.email,
    )
    if not bests:
        return summary
    scores = [b.best_score for b in bests]
    summary.avg_score = round(sum(scores) / len(scores), 1)
    summary.best_score = max(scores)
    summary.exams_taken = len(bests)
    summary.exams_passed = sum(1 for b in bests if b.passed)
    summary.attempts_count = sum(b.attempts for b in bests)
    summary.per_exam = bests
    return summary


def summary_for(db: Session, user: User) -> ExamSummary:
    """Tổng hợp điểm của một người (dùng cho cả `/me` và khi Mentor xem Intern)."""
    return _summary_from_bests(user, _best_rows(db, [user.id]).get(user.id, []))


def overview(db: Session) -> ExamOverview:
    """Điểm trung bình toàn bộ Thực tập sinh (thẻ "Điểm Năng lực TB" của Mentor).

    Trung bình được tính trên những Intern ĐÃ thi ít nhất một bài — cộng cả người
    chưa thi (coi như 0) sẽ kéo con số xuống một cách vô nghĩa.
    """
    interns = list(
        db.scalars(
            select(User)
            .where(
                User.role == Role.INTERN,
                User.deleted_at.is_(None),
            )
            .order_by(User.full_name.asc())
        ).all()
    )
    bests = _best_rows(db, [u.id for u in interns])
    summaries = [_summary_from_bests(u, bests.get(u.id, [])) for u in interns]

    scored = [s.avg_score for s in summaries if s.avg_score is not None]
    summaries.sort(key=lambda s: (s.avg_score is None, -(s.avg_score or 0)))
    return ExamOverview(
        avg_score=round(sum(scored) / len(scored), 1) if scored else None,
        interns_with_attempts=len(scored),
        interns_total=len(interns),
        interns=summaries,
    )
