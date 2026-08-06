"""mentor approval (user_status PENDING) + module deadline + lesson model

Nội dung:
  1. `user_status` thêm giá trị **PENDING** — Mentor tự đăng ký phải chờ ADMIN duyệt
     (`PATCH /users/{id}/approve`).
  2. `modules` thêm `start_date` / `end_date` — hạn của chặng học, frontend hiển thị
     "còn N ngày".
  3. `module_documents` (BÀI HỌC) tự mang `title` + `content_url`, và `document_id`
     trở thành NULL-able: bài học tạo tay (tên + link) không sinh rác trong Thư viện
     Tài liệu. `id` của bảng này vẫn là `module_document_id` mà `lesson_progress`
     và `comments` tham chiếu — KHÔNG đổi khoá.
  4. Bảng mới `lesson_attachments` — tài liệu đính kèm hiển thị ngay dưới bài học.

Viết tay (không autogenerate) vì:
  * `ALTER TYPE ... ADD VALUE` phải chạy ngoài transaction block của Alembic;
  * downgrade cần dựng lại `user_status` không có PENDING và dọn dữ liệu không
    biểu diễn được ở schema cũ (bài học không gắn tài liệu).

Revision ID: 63f0a1c8d4e2
Revises: 1a20809b9ce9
Create Date: 2026-07-27 09:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '63f0a1c8d4e2'
down_revision: Union[str, None] = '1a20809b9ce9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. user_status: thêm PENDING -------------------------------------- #
    # ALTER TYPE ... ADD VALUE không chạy được trong transaction ở PostgreSQL cũ,
    # nên tách ra autocommit block cho an toàn trên mọi phiên bản.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'PENDING'")

    # --- 2. modules: hạn của chặng học ------------------------------------- #
    op.add_column('modules', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('modules', sa.Column('end_date', sa.Date(), nullable=True))

    # --- 3. module_documents: bài học có tên + link riêng ------------------- #
    op.add_column('module_documents', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('module_documents', sa.Column('content_url', sa.Text(), nullable=True))
    op.alter_column('module_documents', 'document_id', existing_type=sa.BigInteger(), nullable=True)

    # --- 4. lesson_attachments --------------------------------------------- #
    op.create_table(
        'lesson_attachments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('module_document_id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['module_document_id'], ['module_documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('module_document_id', 'document_id', name='uq_lesson_attachment'),
    )
    op.create_index(
        op.f('ix_lesson_attachments_document_id'), 'lesson_attachments', ['document_id'],
    )
    op.create_index(
        op.f('ix_lesson_attachments_module_document_id'),
        'lesson_attachments',
        ['module_document_id'],
    )


def downgrade() -> None:
    # --- 4/3/2: bảng và cột ------------------------------------------------- #
    op.drop_index(op.f('ix_lesson_attachments_module_document_id'), table_name='lesson_attachments')
    op.drop_index(op.f('ix_lesson_attachments_document_id'), table_name='lesson_attachments')
    op.drop_table('lesson_attachments')

    # Bài học tạo tay không biểu diễn được ở schema cũ (document_id NOT NULL) -> xoá.
    # Xoá tiến độ/bình luận trỏ tới chúng trước để không vướng khoá ngoại.
    op.execute(
        "DELETE FROM lesson_progress WHERE module_document_id IN "
        "(SELECT id FROM module_documents WHERE document_id IS NULL)"
    )
    op.execute(
        "DELETE FROM comments WHERE module_document_id IN "
        "(SELECT id FROM module_documents WHERE document_id IS NULL)"
    )
    op.execute("DELETE FROM module_documents WHERE document_id IS NULL")
    op.alter_column(
        'module_documents', 'document_id', existing_type=sa.BigInteger(), nullable=False,
    )
    op.drop_column('module_documents', 'content_url')
    op.drop_column('module_documents', 'title')

    op.drop_column('modules', 'end_date')
    op.drop_column('modules', 'start_date')

    # --- 1. user_status: bỏ PENDING ---------------------------------------- #
    # PostgreSQL không xoá được một giá trị enum -> dựng lại kiểu không có PENDING.
    # Tài khoản đang chờ duyệt bị chuyển thành LOCKED (giá trị gần nghĩa nhất).
    op.execute("UPDATE users SET status = 'LOCKED' WHERE status = 'PENDING'")
    op.execute("ALTER TYPE user_status RENAME TO user_status_old")
    op.execute("CREATE TYPE user_status AS ENUM ('ACTIVE', 'LOCKED')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN status TYPE user_status "
        "USING status::text::user_status"
    )
    op.execute("DROP TYPE user_status_old")
