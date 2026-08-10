"""Bootstrap / upsert a user directly in the DB.

Needed to create the FIRST ADMIN (self-registration is disabled and POST /users
requires an existing ADMIN — chicken & egg). Also handy for seeding a MENTOR
while testing.

IMPORTANT: người dùng chỉ đăng nhập được bằng Google, và backend chỉ nhận email
thuộc `ALLOWED_EMAIL_DOMAINS`. Vì vậy email của ADMIN nên nằm trong các tên miền
đó, nếu không tài khoản tạo ra sẽ KHÔNG đăng nhập được (script cảnh báo bên dưới).

Usage (from repo root, venv active):
  python -m scripts.create_user --email admin@gimasys.com --password secret \
      --name "Admin" --role ADMIN
"""
import argparse

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User, UserStatus


def main() -> None:
    ap = argparse.ArgumentParser(description="Create or update a user")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--role", default="ADMIN", choices=[r.value for r in Role])
    args = ap.parse_args()

    # Cảnh báo sớm thay vì để phát hiện lúc không đăng nhập được.
    domain = args.email.strip().lower().rsplit("@", 1)[-1]
    if domain not in settings.allowed_email_domains:
        print(
            f"CANH BAO: '{args.email}' khong thuoc ALLOWED_EMAIL_DOMAINS "
            f"({', '.join(settings.allowed_email_domains)}).\n"
            "  Tai khoan van duoc tao, nhung KHONG dang nhap bang Google duoc.\n"
            "  Sua bang cach dung email thuoc ten mien tren, hoac them ten mien nay "
            "vao ALLOWED_EMAIL_DOMAINS trong .env."
        )

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            user = User(full_name=args.name, email=args.email)
            db.add(user)
            action = "created"
        else:
            action = "updated"
        user.full_name = args.name
        user.password_hash = hash_password(args.password)
        user.role = Role(args.role)
        user.status = UserStatus.ACTIVE
        user.deleted_at = None
        db.commit()
        db.refresh(user)
        print(f"{action} user id={user.id} email={user.email} role={user.role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
