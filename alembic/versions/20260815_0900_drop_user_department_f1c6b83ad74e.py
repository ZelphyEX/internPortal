"""Bỏ cột users.department (Khối kỹ thuật / chuyên ngành của Thực tập sinh)

Cột này chưa bao giờ có đường để nhập: màn "Thêm Thực tập sinh" đã bị bỏ, tài khoản
chỉ sinh ra từ luồng Đăng nhập bằng Google (chỉ hỏi tên), và không có form nào gọi
`PATCH /users/{id}/profile` với `department`. Nên mọi tài khoản thật đều mang giá trị
NULL, trong khi frontend lại mặc định NULL thành "Java Back-End" — hiển thị một
chuyên ngành bịa ra cho tất cả mọi người.

Bỏ khỏi bảng thay vì để cột chết: không có dữ liệu thật nào để mất.

⚠️ Chỉ bỏ `users.department`. Type ENUM `department` VẪN GIỮ vì `modules.track` và
`projects.department` còn dùng — nên `downgrade()` dùng `create_type=False`.

Revision ID: f1c6b83ad74e
Revises: a92f4c17be60
Create Date: 2026-08-15 09:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1c6b83ad74e'
down_revision: Union[str, None] = 'a92f4c17be60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEPARTMENT_VALUES = (
    'Java Back-End',
    'React Front-End',
    'Cloud & DevOps',
    'Salesforce/ERP',
    'AI & Data Science',
)


def upgrade() -> None:
    op.drop_column('users', 'department')


def downgrade() -> None:
    # Dựng lại cấu trúc; dữ liệu cũ KHÔNG khôi phục được. `create_type=False` vì
    # type `department` chưa từng bị xoá (modules.track / projects.department dùng).
    op.add_column(
        'users',
        sa.Column(
            'department',
            postgresql.ENUM(*DEPARTMENT_VALUES, name='department', create_type=False),
            nullable=True,
        ),
    )
