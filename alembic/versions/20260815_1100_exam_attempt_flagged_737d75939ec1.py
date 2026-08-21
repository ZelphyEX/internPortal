"""add flagged to exam_attempts

Lưu danh sách số câu người thi tự đánh dấu "xem lại sau" (lá cờ) — [3, 17, 42].
Không liên quan đúng/sai, chỉ là ghi chú riêng của người làm bài; lưu để khi xem
lại còn thấy mình đã băn khoăn ở những câu nào.

Nullable, không backfill: các lần thi trước cột này không có dữ liệu cờ (cờ chỉ
tồn tại trong bộ nhớ trình duyệt lúc làm bài, chưa từng gửi lên server), nên
không có gì để lấy lại.

Revision ID: 737d75939ec1
Revises: bf0f2f0ed01d
Create Date: 2026-08-15 11:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '737d75939ec1'
down_revision: Union[str, None] = 'bf0f2f0ed01d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'exam_attempts',
        sa.Column('flagged', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('exam_attempts', 'flagged')
