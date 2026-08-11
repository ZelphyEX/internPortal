"""project_members.source_group_id + bỏ các trường hành chính của user

Hai thay đổi:

1. **`project_members.source_group_id`** — ghi lại "người này vào dự án vì thuộc
   nhóm X", đối xứng với `roadmap_assignments.source_group_id` đã có. Nhờ cột này,
   gán một NHÓM vào dự án/lộ trình trở thành *luật thường trực*: ai vào nhóm sau
   cũng tự được thêm, và khi rời nhóm chỉ gỡ đúng phần đến từ nhóm.

2. **Bỏ khối "Thông tin Hành chính & Đào tạo" khỏi `users`**: `phone`, `university`,
   `mentor_id`, `start_date`, `end_date`. Các trường này không còn hiển thị ở đâu.
   `major`, `bio`, `github_url`, `department`, `score`, `attendance_rate` GIỮ NGUYÊN.

⚠️ Bước 2 **xoá dữ liệu vĩnh viễn**. `downgrade()` dựng lại cột nhưng giá trị cũ
không lấy lại được (số điện thoại, trường, mentor phụ trách, thời gian thực tập).
Nếu cần giữ, sao lưu bảng `users` trước khi chạy.

Revision ID: d5c8a2e64f19
Revises: b3f19c90f2d8
Create Date: 2026-08-12 09:00:00.000000+00:00

Ghi chú: bản này ban đầu nối vào `a4e19f70c2b8`, trùng với `b3f19c90f2d8`
(add mode to exam_attempts) được tạo song song -> Alembic có HAI head và
`alembic upgrade head` báo lỗi, khiến container Cloud Run không khởi động được.
Đã nối lại thành một chuỗi thẳng: a4e19f70c2b8 -> b3f19c90f2d8 -> d5c8a2e64f19.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5c8a2e64f19'
down_revision: Union[str, None] = 'b3f19c90f2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. project_members: nguồn nhóm ------------------------------------ #
    op.add_column(
        'project_members', sa.Column('source_group_id', sa.BigInteger(), nullable=True),
    )
    op.create_index(
        'ix_project_members_source_group_id', 'project_members', ['source_group_id'],
    )
    op.create_foreign_key(
        'fk_project_members_source_group_id_groups',
        'project_members', 'groups', ['source_group_id'], ['id'],
    )

    # --- 2. users: bỏ khối hành chính -------------------------------------- #
    # mentor_id có FK + index tự sinh, drop_column dọn kèm.
    for column in ('mentor_id', 'phone', 'university', 'start_date', 'end_date'):
        op.drop_column('users', column)


def downgrade() -> None:
    # Dựng lại cấu trúc; dữ liệu cũ KHÔNG khôi phục được.
    op.add_column('users', sa.Column('end_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('university', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('mentor_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_users_mentor_id', 'users', ['mentor_id'])
    op.create_foreign_key(
        'fk_users_mentor_id_users', 'users', 'users', ['mentor_id'], ['id'],
    )

    op.drop_constraint(
        'fk_project_members_source_group_id_groups', 'project_members', type_='foreignkey',
    )
    op.drop_index('ix_project_members_source_group_id', table_name='project_members')
    op.drop_column('project_members', 'source_group_id')
