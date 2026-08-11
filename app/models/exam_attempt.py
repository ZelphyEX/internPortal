"""Kết quả một lần thi thử Anthropic Mock Exam (chế độ THI, không phải luyện tập).

Trước đây điểm chỉ nằm trong `localStorage` của từng trình duyệt, nên Mentor không
xem được điểm của Thực tập sinh và đổi máy là mất điểm. Bảng này là nguồn sự thật.

Mỗi lần nộp bài ở chế độ thi tạo MỘT dòng (giữ lịch sử). "Điểm của một bài thi" =
điểm cao nhất trong các lần làm bài đó; xem `app.services.exam_service`.

Đề thi nằm ở frontend (`src/data/CF.tests/`), server không có đáp án nên KHÔNG tự
chấm lại được. Vì vậy client gửi `correct_count`/`total_questions` và server tự tính
`score` từ đó (client không đặt điểm trực tiếp).
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (
        # Phục vụ truy vấn "điểm tốt nhất mỗi đề của mỗi người"
        # (GROUP BY user_id, exam_id) ở Dashboard.
        Index("ix_exam_attempts_user_exam", "user_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False,
    )
    # Id đề thi phía frontend, vd "claude-dev-1". Không có FK vì đề là dữ liệu tĩnh
    # trong bundle client, không phải bảng trong DB.
    exam_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    exam_title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nhãn nhóm đề, vd "Claude Developer" / "Claude Foundation".
    exam_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Điểm quy đổi 0..1000 — server tính, xem exam_service.scaled_score().
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Đúng >= 80% số câu (exam_service.is_passing). Lưu sẵn để thống kê khỏi tính lại.
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: Số giây thực tế đã dùng (nếu client gửi). Giới hạn đề là 120 phút.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Chế độ làm bài: "exam" (thi thật) hoặc "practice" (luyện tập)
    mode: Mapped[str] = mapped_column(String(50), default="exam", server_default="exam", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped[User] = relationship(User, lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ExamAttempt id={self.id} user_id={self.user_id} "
            f"exam_id={self.exam_id!r} score={self.score}>"
        )
