"""Bỏ cột users.major (Ngành học)

Trường "Ngành" không còn hiển thị ở đâu trong portal (hồ sơ Thực tập sinh chỉ còn
Email + Định hướng), và cũng không còn được hỏi lúc đăng ký — nên bỏ khỏi bảng thay
vì để một cột chết mà lần đọc nào cũng phải mang theo.

⚠️ Xoá dữ liệu vĩnh viễn. `downgrade()` dựng lại cột nhưng giá trị cũ không lấy lại
được. Sao lưu `users` trước nếu ngành học đang có dữ liệu thật.

Revision ID: e7a4b1d09c53
Revises: d5c8a2e64f19
Create Date: 2026-08-13 09:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7a4b1d09c53'
down_revision: Union[str, None] = 'd5c8a2e64f19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('users', 'major')


def downgrade() -> None:
    # Dựng lại cấu trúc; dữ liệu cũ KHÔNG khôi phục được.
    op.add_column('users', sa.Column('major', sa.String(length=255), nullable=True))
