"""Bootstrap / upsert a user directly in the DB.

Needed to create the FIRST ADMIN (register only makes INTERN, and
POST /users requires an existing ADMIN — chicken & egg). Also handy for
seeding a MENTOR while testing.

Usage (from repo root, venv active):
  python -m scripts.create_user --email admin@portal.test --password secret \
      --name "Admin" --role ADMIN
"""
import argparse

from sqlalchemy import select

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
