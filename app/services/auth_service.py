"""Auth business logic (đăng nhập Google / refresh / logout / password).

Routers stay thin — they call these functions. Security rules:
  * passwords are bcrypt-hashed (never stored raw)
  * refresh tokens are stored as SHA-256 hashes in `refresh_tokens`
  * changing the password revokes all of the user's refresh tokens

Cách vào hệ thống DUY NHẤT của người dùng là **Đăng nhập bằng Google**
(`POST /auth/google` → nếu chưa có tài khoản thì `POST /auth/google/complete`).
OAuth Consent Screen đang là "External" nên Google không tự chặn tên miền —
việc chặn nằm ở `_validate_email_domain` bên dưới.
"""
import secrets
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.auth import RefreshToken
from app.models.user import Role, User, UserStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_active_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )


def _domain_of(email: str) -> str:
    return email.lower().strip().rsplit("@", 1)[-1]


def _validate_email_domain(email: str) -> None:
    """Chỉ cho phép email thuộc `settings.ALLOWED_EMAIL_DOMAINS`.

    Đây là chốt duy nhất chặn tài khoản Gmail cá nhân: Consent Screen "External"
    cho phép mọi người bấm đăng nhập, nên nếu bỏ hàm này thì ai cũng vào được.
    """
    allowed = settings.allowed_email_domains
    if _domain_of(email) in allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Chỉ chấp nhận email nội bộ Gimasys ("
            + ", ".join(f"@{d}" for d in allowed)
            + "). Vui lòng đăng nhập bằng tài khoản Google của công ty hoặc nhà trường."
        ),
    )


def role_for_email(email: str) -> tuple[Role, UserStatus]:
    """Vai trò + trạng thái khởi tạo cho tài khoản mới.

    **Ai đăng nhập lần đầu cũng là INTERN và dùng được portal ngay.** Tên miền
    email KHÔNG còn quyết định vai trò nữa.

    Trước đây `@gimasys.com` được cấp MENTOR ở trạng thái PENDING, dẫn tới hai hệ quả
    xấu: nhân viên mới bị chặn ngoài cửa cho tới khi Admin duyệt, và hệ thống có HAI
    đường lên Mentor (theo tên miền + theo yêu cầu chuyển vai trò) dễ lệch nhau.
    Nay chỉ còn một đường duy nhất: `POST /role-requests` -> Admin duyệt
    (xem `role_request_service`).
    """
    return Role.INTERN, UserStatus.ACTIVE


#: Thông báo dùng chung khi tài khoản MENTOR chưa được duyệt. Frontend dựa vào
#: chuỗi mã `PENDING_APPROVAL` để chuyển sang màn "đang chờ duyệt".
PENDING_APPROVAL_DETAIL = (
    "PENDING_APPROVAL: Tài khoản Mentor của bạn đang chờ Quản trị viên duyệt."
)


def _free_soft_deleted_email(db: Session, email: str) -> None:
    """Đổi tên email của bản ghi đã xoá mềm để giải phóng UNIQUE index.

    Nhờ vậy một người từng bị xoá tài khoản vẫn đăng ký lại được bằng email cũ.
    """
    soft_deleted = db.scalar(
        select(User).where(User.email == email, User.deleted_at.is_not(None))
    )
    if soft_deleted is not None:
        soft_deleted.email = f"{soft_deleted.email}_deleted_{int(_now().timestamp())}"
        db.add(soft_deleted)
        db.commit()


def _assert_email_free(db: Session, email: str) -> None:
    if db.scalar(
        select(User.id).where(User.email == email, User.deleted_at.is_(None))
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered",
        )


def authenticate(db: Session, email: str, password: str) -> User:
    """Đăng nhập bằng mật khẩu — CHỈ dành cho tài khoản Quản trị viên.

    Intern/Mentor bắt buộc đi qua Google: tài khoản của họ sinh ra từ luồng Google
    và mang mật khẩu ngẫu nhiên không ai biết. Chặn ở đây để đường mật khẩu không
    trở thành lối đi vòng qua xác thực Google cho các vai trò khác.
    """
    _validate_email_domain(email)
    user = _get_active_user_by_email(db, email)
    # Same 401 for unknown email and wrong password (no user enumeration).
    if user is None or not security.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu.",
        )
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Ô đăng nhập mật khẩu chỉ dành cho tài khoản Quản trị viên. "
                'Vui lòng dùng nút "Đăng nhập bằng Google".'
            ),
        )
    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PENDING_APPROVAL_DETAIL,
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị khóa.",
        )
    return user


# --------------------------------------------------------------------------- #
# Đăng nhập bằng Google (đường vào duy nhất của người dùng)
# --------------------------------------------------------------------------- #
def _mock_google_identity(credential: str) -> dict:
    """Chỉ dùng cho dev: `mock_google_token_<email>_<Ho-Ten>`."""
    parts = credential.split("_")
    email = parts[3] if len(parts) >= 4 else "demo@edu.gimasys.com"
    name = parts[4].replace("-", " ") if len(parts) > 4 else "Demo Google User"
    return {"email": email.lower().strip(), "full_name": name, "avatar_url": None}


def _verify_google_credential(credential: str) -> dict:
    """Xác thực Google ID token, trả về {email, full_name, avatar_url}.

    Không bao giờ tin dữ liệu client gửi lên: email lấy từ token đã được Google
    ký, không lấy từ body request.
    """
    if not settings.GOOGLE_CLIENT_ID:
        # Trước đây nhánh này tự nhận mọi "mock token" — nghĩa là khi thiếu biến
        # môi trường thì bất kỳ ai cũng đăng nhập được bằng email bất kỳ (kể cả
        # tài khoản Admin). Giờ phải bật cờ ALLOW_MOCK_GOOGLE_LOGIN mới cho phép.
        if settings.ALLOW_MOCK_GOOGLE_LOGIN:
            return _mock_google_identity(credential)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Máy chủ chưa cấu hình GOOGLE_CLIENT_ID nên chưa xác thực được "
                "tài khoản Google. Vui lòng liên hệ bộ phận kỹ thuật."
            ),
        )

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        idinfo = id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID.strip(),
        )
    except Exception:
        # Không đẩy chi tiết lỗi thư viện ra ngoài (tránh lộ cấu hình nội bộ).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Xác thực Google thất bại. Vui lòng thử đăng nhập lại.",
        )

    email = str(idinfo.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản Google không cung cấp địa chỉ email.",
        )
    if idinfo.get("email_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email của tài khoản Google này chưa được xác thực.",
        )
    return {
        "email": email,
        "full_name": idinfo.get("name") or email.split("@")[0],
        "avatar_url": idinfo.get("picture"),
    }


#: Kết quả của `google_sign_in`.
GOOGLE_AUTHENTICATED = "AUTHENTICATED"
GOOGLE_NEEDS_REGISTRATION = "NEEDS_REGISTRATION"


def google_sign_in(db: Session, credential: str) -> tuple[str, User | None, dict]:
    """Xác thực Google rồi tra tài khoản.

    Trả về `(GOOGLE_AUTHENTICATED, user, identity)` nếu đã có tài khoản, hoặc
    `(GOOGLE_NEEDS_REGISTRATION, None, identity)` nếu chưa — khi đó router cấp
    một "vé đăng ký" để frontend hiện form nhập hồ sơ.

    Cố tình KHÔNG tự tạo tài khoản ở đây: hồ sơ (đơn vị, trường, SĐT...) phải do
    người dùng nhập, và tài khoản Mentor còn cần Admin duyệt.
    """
    identity = _verify_google_credential(credential)
    _validate_email_domain(identity["email"])

    user = _get_active_user_by_email(db, identity["email"])
    if user is None:
        return GOOGLE_NEEDS_REGISTRATION, None, identity

    # Mentor chưa được duyệt thì vẫn phải chờ. Trước đây nhánh này tự đặt ACTIVE,
    # tức là chỉ cần đăng nhập bằng Google là bỏ qua được bước Admin duyệt.
    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PENDING_APPROVAL_DETAIL,
        )
    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị khóa.",
        )

    # Lần đầu chuyển sang đăng nhập Google: lấy luôn ảnh đại diện nếu còn trống.
    if not user.avatar_url and identity.get("avatar_url"):
        user.avatar_url = identity["avatar_url"]
        db.commit()
        db.refresh(user)
    return GOOGLE_AUTHENTICATED, user, identity


def complete_google_signup(
    db: Session, *, signup_ticket: str, full_name: str,
) -> User:
    """Tạo tài khoản sau khi người dùng xác nhận họ tên (bước 2 của đăng nhập Google).

    Chỉ cần họ tên. Hồ sơ chi tiết (SĐT, trường, ngành, đơn vị) để Mentor bổ sung
    sau qua `PATCH /users/{id}/profile` — bắt khai lúc đăng nhập chỉ làm chậm người
    dùng mà phần lớn trường không dùng ngay.

    Email lấy từ vé đăng ký đã ký, KHÔNG lấy từ body — nên không ai đăng ký được
    bằng email của người khác.
    """
    try:
        payload = security.decode_signup_ticket(signup_ticket)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên đăng ký đã hết hạn. Vui lòng bấm Đăng nhập bằng Google lại.",
        )

    email = str(payload.get("sub") or "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Vé đăng ký không hợp lệ.",
        )
    _validate_email_domain(email)
    _free_soft_deleted_email(db, email)
    _assert_email_free(db, email)

    role, initial_status = role_for_email(email)
    user = User(
        full_name=full_name.strip(),
        email=email,
        # Đăng nhập bằng Google nên mật khẩu không dùng tới. Vẫn phải có giá trị
        # (cột NOT NULL) — đặt chuỗi ngẫu nhiên đủ dài để không ai đoán/dò được.
        password_hash=security.hash_password(secrets.token_urlsafe(32)),
        role=role,
        status=initial_status,
        avatar_url=payload.get("picture"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str, datetime]:
    """Return (access_token, raw_refresh_token, session_expires_at).

    Chỉ lưu HASH của refresh token. `session_expires_at` là hạn tuyệt đối của phiên
    (`REFRESH_TOKEN_EXPIRE_DAYS`) — trả về cho client để nó tự đăng xuất đúng lúc
    thay vì đợi một request thất bại mới biết phiên đã chết.
    """
    access = security.create_access_token(subject=user.id, role=user.role.value)
    raw_refresh = security.create_refresh_token()
    expires_at = security.refresh_token_expires_at()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=security.hash_refresh_token(raw_refresh),
        expires_at=expires_at,
    ))
    db.commit()
    return access, raw_refresh, expires_at


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
