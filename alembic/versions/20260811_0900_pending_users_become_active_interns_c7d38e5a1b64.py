"""Mọi tài khoản đang PENDING trở thành Thực tập sinh hoạt động

Đi kèm thay đổi chính sách ở `auth_service.role_for_email`: tên miền email KHÔNG
còn quyết định vai trò nữa — ai đăng nhập lần đầu cũng là INTERN và dùng được ngay.
Đường duy nhất lên MENTOR là yêu cầu chuyển vai trò (`/role-requests`) do ADMIN duyệt.

Vì vậy những người đã đăng ký bằng `@gimasys.com` trước đó đang bị kẹt ở màn "chờ
Quản trị viên duyệt" (`status='PENDING'`) và không vào được portal. Migration này
mở khoá cho họ.

KHÔNG chạm tài khoản ADMIN (dù về lý thuyết không có ADMIN nào ở trạng thái PENDING,
vẫn loại ra cho chắc — không được hạ quyền admin).

Không thể downgrade chính xác: sau khi chạy thì không còn phân biệt được ai vốn là
MENTOR-chờ-duyệt và ai vốn là INTERN. Downgrade để trống có chủ ý.

Revision ID: c7d38e5a1b64
Revises: 8b41f7c2d9a5
Create Date: 2026-08-11 09:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7d38e5a1b64'
down_revision: Union[str, None] = '8b41f7c2d9a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    result = op.get_bind().execute(
        sa.text(
            """
            UPDATE users
               SET role = 'INTERN', status = 'ACTIVE'
             WHERE status = 'PENDING'
               AND role <> 'ADMIN'
               AND deleted_at IS NULL
            """
        )
    )
    print(f"[migration c7d38e5a1b64] mo khoa {result.rowcount} tai khoan dang cho duyet")


def downgrade() -> None:
    # Không phục hồi được: thông tin "ai từng chờ duyệt" đã mất sau khi upgrade.
    pass
