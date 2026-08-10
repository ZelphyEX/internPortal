"""Đồng bộ tài khoản Quản trị viên hệ thống. Chạy mỗi lần container khởi động.

Xem `Dockerfile` CMD: `alembic upgrade head && python -m scripts.ensure_admin && uvicorn ...`

Vì sao cần script này:
  * Người dùng chỉ đăng nhập được bằng Google, và email `@gimasys.com` đăng nhập
    lần đầu sẽ thành MENTOR ở trạng thái chờ duyệt — mà không có ADMIN nào để duyệt.
    Đó là bài toán "con gà - quả trứng", phải có sẵn một ADMIN từ bên ngoài luồng đăng ký.
  * Đặt ở startup (không phải trong migration) nên: chạy lại được, tự sửa nếu tài
    khoản bị khoá/xoá mềm, và quên mật khẩu thì chỉ cần đổi env rồi deploy lại.

Idempotent: chạy bao nhiêu lần cũng cho ra cùng một kết quả. Không in mật khẩu.
Không bao giờ làm sập server: mọi lỗi đều thoát 0 kèm cảnh báo (đặt sau `&&` trong
CMD nên exit code khác 0 sẽ chặn uvicorn khởi động).

Chạy tay (venv active, có DATABASE_URL):
  python -m scripts.ensure_admin
"""
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User, UserStatus

PREFIX = "[ensure_admin]"


def main() -> int:
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    password = settings.BOOTSTRAP_ADMIN_PASSWORD or ""

    if not password:
        print(f"{PREFIX} BOOTSTRAP_ADMIN_PASSWORD chua duoc dat -> bo qua.")
        return 0
    if not email or "@" not in email:
        print(f"{PREFIX} BOOTSTRAP_ADMIN_EMAIL khong hop le ('{email}') -> bo qua.")
        return 0

    # Đăng nhập bằng mật khẩu vẫn đi qua kiểm tra tên miền, nên email admin phải
    # nằm trong ALLOWED_EMAIL_DOMAINS, nếu không tạo ra cũng không đăng nhập được.
    domain = email.rsplit("@", 1)[-1]
    if domain not in settings.allowed_email_domains:
        print(
            f"{PREFIX} CANH BAO: '{email}' ngoai ALLOWED_EMAIL_DOMAINS "
            f"({', '.join(settings.allowed_email_domains)}) -> tao ra nhung KHONG "
            "dang nhap duoc. Sua BOOTSTRAP_ADMIN_EMAIL hoac ALLOWED_EMAIL_DOMAINS."
        )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(full_name=settings.BOOTSTRAP_ADMIN_NAME, email=email)
            db.add(user)
            action = "created"
        else:
            action = "synced"
            # Không ghi đè full_name của tài khoản đã có: admin tự đổi tên hiển thị
            # trong phần Cài đặt thì phải giữ nguyên.

        # Mật khẩu lấy từ env: đây chính là cơ chế "đặt lại mật khẩu admin".
        user.password_hash = hash_password(password)
        user.role = Role.ADMIN
        user.status = UserStatus.ACTIVE
        user.deleted_at = None
        db.commit()
        db.refresh(user)
        print(f"{PREFIX} {action} admin id={user.id} email={user.email}")
        return 0
    except Exception as exc:  # noqa: BLE001 — không được làm sập server vì việc này
        db.rollback()
        print(f"{PREFIX} LOI: khong dong bo duoc tai khoan admin ({type(exc).__name__}: {exc})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
