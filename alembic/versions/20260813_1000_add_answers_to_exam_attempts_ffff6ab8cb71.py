"""add answers to exam_attempts

Lưu lựa chọn của người thi theo từng câu ({"<số câu>": ["A","C"]}), để sau này
xem lại đáp án đã chọn / đáp án đúng / lời giải thích của các lần thi cũ. Đề
(câu hỏi, đáp án đúng, lời giải thích) vẫn tĩnh ở frontend — cột này chỉ lưu
phần lựa chọn để đối chiếu lại với đề đó.

Nullable, không backfill: các lần thi trước cột này tồn tại sẽ không xem lại
chi tiết được, chỉ còn điểm tổng — chấp nhận được vì dữ liệu chi tiết đó chưa
từng tồn tại ở đâu để lấy lại.

Revision ID: ffff6ab8cb71
Revises: c5165ac2fbcd
Create Date: 2026-08-13 10:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ffff6ab8cb71'
down_revision: Union[str, None] = 'c5165ac2fbcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'exam_attempts',
        sa.Column('answers', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('exam_attempts', 'answers')
