"""Nghiệp vụ điểm thi thử Anthropic Mock Exam.

CÁCH TÍNH ĐIỂM (một nơi duy nhất — mọi chỗ khác gọi vào đây):

  * **Mọi câu tính điểm như nhau** (chia đều), không có trọng số theo độ khó.
  * Điểm = tỉ lệ câu đúng quy về **thang 1000**: `round(đúng / tổng * 1000)`.
    Nói cách khác điểm chính là phần trăm nhân 10 (80% -> 800).
  * Đỗ khi đúng **>= 80%** số câu.
  * Đề gồm 60 câu trắc nghiệm (một hoặc nhiều đáp án), làm trong 120 phút.
  * Câu trả lời đúng phải khớp CHÍNH XÁC tập đáp án đúng (client chấm, xem
    `MockExamView.handleSubmitExam`).

Điều kiện đỗ so sánh trên SỐ CÂU (`đúng * 100 >= tổng * 80`) chứ không so trên điểm
đã làm tròn — nếu so trên điểm thì 79,96% làm tròn thành 800 sẽ đỗ oan.
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

#: Thang điểm: 0 (sai hết) .. 1000 (đúng hết).
SCALE_MIN = 0
SCALE_MAX = 1000
#: Phần trăm câu đúng tối thiểu để đỗ.
PASS_PERCENT = 80
#: Điểm tương ứng với PASS_PERCENT trên thang 1000 — chỉ để hiển thị.
PASSING_SCORE = SCALE_MAX * PASS_PERCENT // 100  # 800


def scaled_score(correct_count: int, total_questions: int) -> int:
    """Quy đổi số câu đúng sang thang 0..1000 (chia đều cho mọi câu)."""
    if total_questions <= 0:
        return SCALE_MIN
    ratio = min(1.0, max(0.0, correct_count / total_questions))
    return round(ratio * SCALE_MAX)


def is_passing(correct_count: int, total_questions: int) -> bool:
    """Đỗ khi đúng >= PASS_PERCENT% số câu.

    So sánh bằng số nguyên trên SỐ CÂU, không so trên điểm đã làm tròn: 47/60 =
    78,33% -> 783 điểm (trượt), nhưng nếu so `score >= 800` sau khi làm tròn thì
    một tỉ lệ như 79,96% sẽ thành 800 và đỗ oan.
    """
    if total_questions <= 0:
        return False
    return correct_count * 100 >= total_questions * PASS_PERCENT


def score_is_passing(score: int) -> bool:
    """Dạng chỉ có điểm (dùng cho dữ liệu đã lưu, vd điểm tốt nhất mỗi đề)."""
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
        passed=is_passing(data.correct_count, data.total_questions),
        duration_seconds=data.duration_seconds,
        mode=data.mode,
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
                passed=score_is_passing(row.best_score),
                attempts=row.attempts,
                last_taken_at=row.last_taken_at,
            )
        )
    return grouped


def _summary_from_bests(user: User, bests: list[ExamBest]) -> ExamSummary:
    summary = ExamSummary(
        user_id=user.id, full_name=user.full_name, email=user.email, role=user.role,
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


def overview(db: Session, current_user: User) -> ExamOverview:
    """Điểm trung bình của những người được phép xem (Mentor xem Intern, Admin xem Mentor+Intern).

    Trung bình được tính trên những người ĐÃ thi ít nhất một bài.
    """
    stmt = select(User).where(User.deleted_at.is_(None))
    if current_user.role == Role.ADMIN:
        stmt = stmt.where(User.role.in_([Role.MENTOR, Role.INTERN]))
    else:
        stmt = stmt.where(User.role == Role.INTERN)

    targets = list(
        db.scalars(stmt.order_by(User.full_name.asc())).all()
    )
    bests = _best_rows(db, [u.id for u in targets])
    summaries = [_summary_from_bests(u, bests.get(u.id, [])) for u in targets]

    scored = [s.avg_score for s in summaries if s.avg_score is not None]
    summaries.sort(key=lambda s: (s.avg_score is None, -(s.avg_score or 0)))
    return ExamOverview(
        avg_score=round(sum(scored) / len(scored), 1) if scored else None,
        interns_with_attempts=len(scored),
        interns_total=len(targets),
        interns=summaries,
    )
