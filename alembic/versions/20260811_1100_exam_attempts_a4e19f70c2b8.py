"""exam_attempts — lưu điểm thi thử Anthropic Mock Exam

Trước đây điểm chỉ nằm trong `localStorage` từng trình duyệt: Mentor không xem được
điểm của Thực tập sinh, và đổi máy/xoá cache là mất sạch. Bảng này là nguồn sự thật.

Mỗi lần nộp bài ở CHẾ ĐỘ THI là một dòng (giữ lịch sử). Điểm của một đề = điểm cao
nhất trong các lần làm đề đó. Thang điểm 100..1000, đỗ >= 720 —
xem `app/services/exam_service.py`.

Index `ix_exam_attempts_user_exam` phục vụ truy vấn gom nhóm "điểm tốt nhất mỗi đề
của mỗi người" (GROUP BY user_id, exam_id) ở màn Dashboard.

Revision ID: a4e19f70c2b8
Revises: c7d38e5a1b64
Create Date: 2026-08-11 11:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4e19f70c2b8'
down_revision: Union[str, None] = 'c7d38e5a1b64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exam_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('exam_id', sa.String(length=100), nullable=False),
        sa.Column('exam_title', sa.String(length=255), nullable=False),
        sa.Column('exam_code', sa.String(length=100), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('correct_count', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_exam_attempts_user_id', 'exam_attempts', ['user_id'])
    op.create_index('ix_exam_attempts_exam_id', 'exam_attempts', ['exam_id'])
    op.create_index(
        'ix_exam_attempts_user_exam', 'exam_attempts', ['user_id', 'exam_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_exam_attempts_user_exam', table_name='exam_attempts')
    op.drop_index('ix_exam_attempts_exam_id', table_name='exam_attempts')
    op.drop_index('ix_exam_attempts_user_id', table_name='exam_attempts')
    op.drop_table('exam_attempts')
