"""task_assignees (N-N) thay cho tasks.assigned_intern_id

Một task giờ giao được cho NHIỀU người cùng lúc — vẫn là MỘT bản ghi `tasks` duy
nhất (không tách thành N task riêng), chỉ thêm bảng liên kết N-N người nhận. Ai
trong số người nhận sửa task (status, PR url...) là sửa CHUNG một task, mọi
người còn lại cùng thấy thay đổi ngay.

Backfill: mỗi task đang có `assigned_intern_id` được chuyển thành đúng 1 dòng
`task_assignees` tương ứng, TRƯỚC khi xoá cột cũ — không mất dữ liệu gán hiện có.

Revision ID: bf0f2f0ed01d
Revises: ffff6ab8cb71
Create Date: 2026-08-15 10:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bf0f2f0ed01d'
down_revision: Union[str, None] = 'ffff6ab8cb71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'task_assignees',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'user_id', name='uq_task_assignees_task_user'),
    )
    op.create_index('ix_task_assignees_task_id', 'task_assignees', ['task_id'])
    op.create_index('ix_task_assignees_user_id', 'task_assignees', ['user_id'])

    # Backfill trước khi xoá cột cũ — mỗi task có assigned_intern_id -> 1 dòng.
    op.execute(
        """
        INSERT INTO task_assignees (task_id, user_id, assigned_at)
        SELECT id, assigned_intern_id, COALESCE(updated_at, created_at)
        FROM tasks
        WHERE assigned_intern_id IS NOT NULL
        """
    )

    op.drop_column('tasks', 'assigned_intern_id')


def downgrade() -> None:
    op.add_column('tasks', sa.Column('assigned_intern_id', sa.BigInteger(), nullable=True))

    # Một task lẽ ra có thể có nhiều người ở nhánh mới -> chỉ khôi phục 1 người
    # (người được gán sớm nhất) vì cột cũ chỉ chứa được đúng 1 id.
    op.execute(
        """
        UPDATE tasks t
        SET assigned_intern_id = first_assignee.user_id
        FROM (
            SELECT DISTINCT ON (task_id) task_id, user_id
            FROM task_assignees
            ORDER BY task_id, assigned_at, id
        ) AS first_assignee
        WHERE t.id = first_assignee.task_id
        """
    )

    op.create_index('ix_tasks_assigned_intern_id', 'tasks', ['assigned_intern_id'])
    op.create_foreign_key(
        'tasks_assigned_intern_id_fkey', 'tasks', 'users', ['assigned_intern_id'], ['id'],
    )

    op.drop_index('ix_task_assignees_user_id', table_name='task_assignees')
    op.drop_index('ix_task_assignees_task_id', table_name='task_assignees')
    op.drop_table('task_assignees')
