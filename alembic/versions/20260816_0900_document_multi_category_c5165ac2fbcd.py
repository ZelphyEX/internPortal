"""documents: category (1 giá trị) -> categories (nhiều giá trị)

Thư viện Tài liệu trước đây chỉ gán được MỘT danh mục cho mỗi tài liệu
(`documents.category`, string đơn). Một tài liệu thực tế lại thường thuộc nhiều
danh mục cùng lúc (vd. vừa là "CCA-F Certificate" vừa là "Coding Standard"), nên
đổi sang mảng `categories` — cùng khuôn JSONB đã dùng cho `modules.key_skills`
(migration 1a20809b9ce9): mảng string, thay toàn bộ mỗi lần sửa, không có bảng
phụ vì danh mục là tập cố định do frontend định nghĩa (`DOC_CATEGORIES`), không
cần tra cứu/đếm số lượng dùng như `tags`.

Dữ liệu cũ: tài liệu đã có `category` được chuyển thành mảng 1 phần tử; tài liệu
chưa gán danh mục (NULL) thành mảng rỗng `[]`.

Revision ID: c5165ac2fbcd
Revises: f1c6b83ad74e
Create Date: 2026-08-16 09:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c5165ac2fbcd'
down_revision: Union[str, None] = 'f1c6b83ad74e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column(
            'categories',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # Backfill: category='X' -> categories=["X"]; NULL/'' -> categories=[] (đã
    # có sẵn từ server_default, chỉ cần xử lý phần có giá trị thật).
    op.execute(
        "UPDATE documents SET categories = jsonb_build_array(category) "
        "WHERE category IS NOT NULL AND category != ''"
    )
    op.drop_index('ix_documents_category', table_name='documents')
    op.drop_column('documents', 'category')


def downgrade() -> None:
    op.add_column('documents', sa.Column('category', sa.String(length=100), nullable=True))
    op.create_index('ix_documents_category', 'documents', ['category'])
    # Chỉ khôi phục được PHẦN TỬ ĐẦU — hạ cấp mất thông tin nếu tài liệu đang có
    # từ 2 danh mục trở lên, không có cách nào dồn nhiều giá trị về một cột đơn.
    op.execute(
        "UPDATE documents SET category = categories->>0 "
        "WHERE jsonb_array_length(categories) > 0"
    )
    op.drop_column('documents', 'categories')
