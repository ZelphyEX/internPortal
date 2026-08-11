"""documents: thêm category / file_type / file_size_bytes

Sửa lỗi Thư viện Tài liệu mất thông tin sau khi tải lại trang.

Nguyên nhân: bảng `documents` chỉ có `type` với 4 giá trị (VIDEO/PDF/LINK/ARTICLE),
không có chỗ nào lưu **danh mục** và **dung lượng**, còn **định dạng thật** mà giao
diện hiển thị (PDF/DOCX/SLIDE/MD) thì không biểu diễn được — DOCX và MD đều bị dồn
về ARTICLE. Kết quả: mọi tài liệu tải lại đều rơi về danh mục mặc định "API Docs",
định dạng sai và dung lượng hiện "—".

Ba cột mới đều nullable nên tài liệu cũ không bị ảnh hưởng; frontend vẫn suy ra từ
`type` khi `file_type` là NULL (xem `apiDocumentToResource`).

Revision ID: a92f4c17be60
Revises: e7a4b1d09c53
Create Date: 2026-08-14 09:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a92f4c17be60'
down_revision: Union[str, None] = 'e7a4b1d09c53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('category', sa.String(length=100), nullable=True))
    op.add_column('documents', sa.Column('file_type', sa.String(length=20), nullable=True))
    op.add_column('documents', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))
    # Lọc theo danh mục là thao tác thường xuyên nhất ở màn Thư viện.
    op.create_index('ix_documents_category', 'documents', ['category'])


def downgrade() -> None:
    op.drop_index('ix_documents_category', table_name='documents')
    op.drop_column('documents', 'file_size_bytes')
    op.drop_column('documents', 'file_type')
    op.drop_column('documents', 'category')
