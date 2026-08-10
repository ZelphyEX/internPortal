"""role_change_requests — yêu cầu chuyển vai trò Thực tập sinh <-> Mentor

Nội dung:
  1. ENUM mới `role_request_status` (PENDING / APPROVED / REJECTED / CANCELLED).
  2. Bảng `role_change_requests`: ai xin đổi từ vai trò nào sang vai trò nào, ai
     duyệt, duyệt lúc nào.
  3. Unique index CÓ ĐIỀU KIỆN `uq_role_change_requests_one_pending`: mỗi người
     chỉ có tối đa một yêu cầu đang chờ duyệt. Đặt ở DB để hai request gửi song
     song (bấm 2 tab) cũng không tạo được yêu cầu trùng.

`from_role` / `to_role` dùng lại ENUM `user_role` đã có nên KHÔNG tạo type mới
(`postgresql.ENUM(..., create_type=False)`).

Revision ID: 8b41f7c2d9a5
Revises: 63f0a1c8d4e2
Create Date: 2026-08-10 10:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8b41f7c2d9a5'
down_revision: Union[str, None] = '63f0a1c8d4e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ENUM đã tồn tại từ migration đầu tiên -> chỉ tham chiếu, không CREATE TYPE lại.
USER_ROLE = postgresql.ENUM(
    'ADMIN', 'MENTOR', 'INTERN', name='user_role', create_type=False,
)
ROLE_REQUEST_STATUS = postgresql.ENUM(
    'PENDING', 'APPROVED', 'REJECTED', 'CANCELLED',
    name='role_request_status',
    create_type=False,
)


def upgrade() -> None:
    # create_type=False ở trên nên phải tự tạo type mới một lần, checkfirst để
    # chạy lại migration trên DB đã có type cũng không lỗi.
    ROLE_REQUEST_STATUS.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'role_change_requests',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('from_role', USER_ROLE, nullable=False),
        sa.Column('to_role', USER_ROLE, nullable=False),
        sa.Column('status', ROLE_REQUEST_STATUS, nullable=False,
                  server_default='PENDING'),
        sa.Column('decided_by', sa.BigInteger(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_role_change_requests_user_id', 'role_change_requests', ['user_id'],
    )
    op.create_index(
        'uq_role_change_requests_one_pending',
        'role_change_requests',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index('uq_role_change_requests_one_pending', table_name='role_change_requests')
    op.drop_index('ix_role_change_requests_user_id', table_name='role_change_requests')
    op.drop_table('role_change_requests')
    ROLE_REQUEST_STATUS.drop(op.get_bind(), checkfirst=True)
