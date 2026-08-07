"""Delete a user directly from the DB by email.

Usage (from repo root, venv active):
  python -m scripts.delete_user --email test@edu.gimasys.com
"""
import argparse
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.user import User

def main() -> None:
    ap = argparse.ArgumentParser(description="Delete a user by email")
    ap.add_argument("--email", required=True)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is not None:
            db.delete(user)
            db.commit()
            print(f"Successfully deleted user: {args.email}")
        else:
            print(f"User with email {args.email} not found in database.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
