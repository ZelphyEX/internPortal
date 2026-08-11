"""Schemas cho điểm thi thử Anthropic Mock Exam."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamAttemptCreate(BaseModel):
    """Nộp kết quả một lần thi ở CHẾ ĐỘ THI.

    Client KHÔNG gửi `score`: server tự tính từ `correct_count`/`total_questions`
    để công thức chỉ tồn tại ở một nơi và client không tự đặt điểm cho mình.
    (Server vẫn không có đáp án để chấm lại — xem ghi chú ở `models/exam_attempt.py`.)
    """
    exam_id: str = Field(min_length=1, max_length=100)
    exam_title: str = Field(min_length=1, max_length=255)
    exam_code: str | None = Field(default=None, max_length=100)
    total_questions: int = Field(gt=0, le=500)
    correct_count: int = Field(ge=0, le=500)
    duration_seconds: int | None = Field(default=None, ge=0, le=24 * 3600)
    mode: str = Field(default="exam", max_length=50)


class ExamAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    exam_id: str
    exam_title: str
    exam_code: str | None = None
    total_questions: int
    correct_count: int
    score: int
    passed: bool
    duration_seconds: int | None = None
    mode: str
    created_at: datetime


class ExamBest(BaseModel):
    """Kết quả TỐT NHẤT của một người ở một đề thi."""
    exam_id: str
    exam_title: str
    exam_code: str | None = None
    best_score: int
    passed: bool
    attempts: int
    last_taken_at: datetime


from app.models.user import Role


class ExamSummary(BaseModel):
    """Tổng hợp điểm thi của MỘT người.

    `avg_score` tính trên **điểm tốt nhất của mỗi đề** (không phải trung bình mọi
    lần làm) — làm lại một đề nhiều lần không kéo trung bình xuống.
    """
    user_id: int
    full_name: str | None = None
    email: str | None = None
    role: Role | None = None
    #: None nếu chưa thi bài nào ở chế độ thi.
    avg_score: float | None = None
    best_score: int | None = None
    exams_taken: int = 0
    exams_passed: int = 0
    attempts_count: int = 0
    per_exam: list[ExamBest] = []


class ExamOverview(BaseModel):
    """Tổng hợp cho Mentor/Admin: điểm trung bình toàn bộ Thực tập sinh."""
    #: Trung bình của `avg_score` trên các Thực tập sinh ĐÃ thi ít nhất 1 bài.
    avg_score: float | None = None
    #: Số Thực tập sinh đã thi ít nhất 1 bài / tổng số Thực tập sinh.
    interns_with_attempts: int = 0
    interns_total: int = 0
    #: Xếp theo điểm trung bình giảm dần; người chưa thi nằm cuối.
    interns: list[ExamSummary] = []
