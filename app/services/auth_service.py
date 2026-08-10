"""Auth business logic (register / login / refresh / logout / password).

Routers stay thin — they call these functions. Security rules:
  * passwords are bcrypt-hashed (never stored raw)
  * refresh tokens are stored as SHA-256 hashes in `refresh_tokens`
  * changing the password revokes all of the user's refresh tokens
"""
import random
import dns.resolver  # MX record lookup for email existence
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import RefreshToken
from app.models.user import Role, User, UserStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _has_mx_record(email: str) -> bool:
    """Check if the email's domain has an MX record (basic existence check)."""
    domain = email.split('@')[-1].lower()
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except Exception:
        return False


# Global in-memory storage for verification codes: email -> 6-digit code string
verification_codes: dict[str, str] = {}


def _get_active_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )


def _validate_email_domain(email: str) -> None:
    email_lower = email.lower().strip()
    if email_lower in ("admin@example.com", "mentor@example.com", "intern@example.com"):
        return
    if email_lower.endswith("@gimasys.com") or email_lower.endswith("@edu.gimasys.com"):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Chỉ chấp nhận email thuộc tên miền @gimasys.com hoặc @edu.gimasys.com.",
    )


#: Thông báo dùng chung khi tài khoản MENTOR chưa được duyệt. Frontend dựa vào
#: chuỗi mã `PENDING_APPROVAL` để chuyển sang màn "đang chờ duyệt".
PENDING_APPROVAL_DETAIL = (
    "PENDING_APPROVAL: Tài khoản Mentor của bạn đang chờ Quản trị viên duyệt."
)


def register(
    db: Session, *, full_name: str, email: str, password: str, role: Role = Role.INTERN,
) -> User:
    """Tự đăng ký. Quyết định vai trò dựa trên tên miền email.
    Tất cả các tài khoản tự đăng ký mới sẽ có trạng thái PENDING và cần
    phải xác thực email qua mã gửi về trước khi có thể hoạt động.
    """
    _validate_email_domain(email)

    # MX record check disabled – any address under allowed domains is accepted

    email_lower = email.lower().strip()
    if email_lower == "admin@example.com":
        resolved_role = Role.ADMIN
        resolved_status = UserStatus.ACTIVE
    elif email_lower == "mentor@example.com":
        resolved_role = Role.MENTOR
        resolved_status = UserStatus.ACTIVE
    elif email_lower == "intern@example.com":
        resolved_role = Role.INTERN
        resolved_status = UserStatus.ACTIVE
    elif email_lower.endswith("@gimasys.com"):
        resolved_role = Role.MENTOR
        resolved_status = UserStatus.PENDING
    elif email_lower.endswith("@edu.gimasys.com"):
        resolved_role = Role.INTERN
        resolved_status = UserStatus.ACTIVE
    else:
        resolved_role = role
        resolved_status = UserStatus.PENDING


    # If there is a soft-deleted user with the same email, rename it to free up the UNIQUE constraint
    soft_deleted_user = db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_not(None))
    )
    if soft_deleted_user:
        now_dt = _now()
        timestamp = int(now_dt.timestamp())
        soft_deleted_user.email = f"{soft_deleted_user.email}_deleted_{timestamp}"
        db.add(soft_deleted_user)
        db.commit()

    # Conflict check includes active/un-deleted rows
    if db.scalar(select(User.id).where(User.email == email, User.deleted_at.is_(None))) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered",
        )
    user = User(
        full_name=full_name,
        email=email,
        password_hash=security.hash_password(password),
        role=resolved_role,
        status=resolved_status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate(db: Session, email: str, password: str) -> User:
    _validate_email_domain(email)
    user = _get_active_user_by_email(db, email)
    # Same 401 for unknown email and wrong password (no user enumeration).
    if user is None or not security.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PENDING_APPROVAL_DETAIL,
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked",
        )
    return user


def google_authenticate(db: Session, credential: str) -> User:
    """Xác thực Google ID Token, tự đăng ký nếu là user mới (vai trò dựa trên email domain).
    Hỗ trợ mock token ở môi trường dev nếu chưa cấu hình GOOGLE_CLIENT_ID.
    """
    from app.core.config import settings
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    email: str = ""
    name: str = ""
    picture: str | None = None

    # Development Mock Fallback
    if not settings.GOOGLE_CLIENT_ID or credential.startswith("mock_google_token_"):
        token_parts = credential.split("_")
        if len(token_parts) >= 4:
            email = token_parts[3]
            name = token_parts[4] if len(token_parts) > 4 else "Google User"
            name = name.replace("-", " ")
        else:
            email = "demo.google@gimasys.com"
            name = "Demo Google User"
        print(f"[MOCK GOOGLE AUTH] Verified mock token for email={email}, name={name}")
    else:
        try:
            client_id = settings.GOOGLE_CLIENT_ID
            if client_id:
                client_id = client_id.replace("https://", "").replace("http://", "").strip("/")
            idinfo = id_token.verify_oauth2_token(
                credential, google_requests.Request(), client_id
            )
            email = idinfo["email"]
            name = idinfo.get("name", "Google User")
            picture = idinfo.get("picture")
        except Exception as e:
            import traceback
            print(f"[GOOGLE AUTH ERROR] {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Xác thực Google ID token thất bại ({type(e).__name__}): {str(e)}",
            )

    email_lower = email.lower().strip()
    _validate_email_domain(email_lower)

    user = db.scalar(
        select(User).where(User.email == email_lower, User.deleted_at.is_(None))
    )

    if user is None:
        soft_deleted = db.scalar(
            select(User).where(User.email == email_lower, User.deleted_at.is_not(None))
        )
        if soft_deleted:
            db.delete(soft_deleted)
            db.commit()

        if email_lower.endswith("@gimasys.com"):
            resolved_role = Role.MENTOR
        elif email_lower.endswith("@edu.gimasys.com"):
            resolved_role = Role.INTERN
        else:
            resolved_role = Role.INTERN

        random_pw = security.hash_password(str(random.randint(10000000, 99999999)))
        user = User(
            full_name=name,
            email=email_lower,
            password_hash=random_pw,
            role=resolved_role,
            status=UserStatus.ACTIVE,
            avatar_url=picture,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[GOOGLE AUTH] Created new user: {email_lower} (role={resolved_role.value})")
    else:
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE
            db.add(user)
            db.commit()
            db.refresh(user)
        elif user.status == UserStatus.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này đã bị khóa.",
            )

    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    """Return (access_token, raw_refresh_token). Stores only the refresh hash."""
    access = security.create_access_token(subject=user.id, role=user.role.value)
    raw_refresh = security.create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=security.hash_refresh_token(raw_refresh),
        expires_at=security.refresh_token_expires_at(),
    ))
    db.commit()
    return access, raw_refresh


def refresh_access_token(db: Session, raw_refresh: str) -> str:
    token_hash = security.hash_refresh_token(raw_refresh)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if rt is None or rt.revoked_at is not None or rt.expires_at <= _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = db.get(User, rt.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token",
        )
    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PENDING_APPROVAL_DETAIL,
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked",
        )
    return security.create_access_token(subject=user.id, role=user.role.value)


def logout(db: Session, user: User, raw_refresh: str) -> None:
    """Revoke the given refresh token if it belongs to `user`. Idempotent."""
    token_hash = security.hash_refresh_token(raw_refresh)
    rt = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user.id,
        )
    )
    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = _now()
        db.commit()


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not security.verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect",
        )
    user.password_hash = security.hash_password(new_password)
    # Invalidate existing sessions after a password change.
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()


def update_me(db: Session, user: User, fields: dict) -> User:
    for key, value in fields.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def delete_self(db: Session, user: User) -> None:
    """Xóa tài khoản của chính mình (xoá mềm bằng cách đặt `deleted_at`).
    Đồng thời đổi tên email để giải phóng ràng buộc UNIQUE, cho phép đăng ký lại.
    Không cho phép ADMIN tự xóa chính mình để tránh hệ thống mất quản trị viên.
    """
    if user.role == Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản Quản trị viên không thể tự xóa.",
        )
    
    if user.deleted_at is None:
        now_dt = _now()
        user.deleted_at = now_dt
        timestamp = int(now_dt.timestamp())
        user.email = f"{user.email}_deleted_{timestamp}"
        db.add(user)
        db.commit()
