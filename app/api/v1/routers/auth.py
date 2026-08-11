from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.deps import CurrentUser, DbSession
from app.models.user import User, UserStatus
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    GoogleAuthResponse,
    GoogleLoginRequest,
    GoogleProfile,
    GoogleSignupRequest,
    LoginRequest,
    LoginUser,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.user import MeOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

#: Đăng ký bằng email + mật khẩu đã bị tắt: cách duy nhất để có tài khoản là
#: đăng nhập bằng Google (server tự xác thực email thuộc tên miền Gimasys).
_REGISTRATION_DISABLED = (
    "Đăng ký bằng mật khẩu đã bị tắt. Vui lòng dùng nút "
    '"Đăng nhập bằng Google" với email @gimasys.com hoặc @edu.gimasys.com.'
)


@router.post("/register", deprecated=True)
def register_disabled() -> None:
    """**Đã tắt** (403). Trước đây endpoint này cho tự đăng ký bằng mật khẩu, nghĩa
    là ai cũng tạo được tài khoản mang email của người khác vì email không hề được
    xác thực. Giờ tài khoản chỉ sinh ra từ luồng Google (`POST /auth/google`)."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail=_REGISTRATION_DISABLED,
    )


def _token_response(db: Session, user: User) -> TokenResponse:
    access, refresh, session_expires_at = auth_service.issue_tokens(db, user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        user=LoginUser.model_validate(user),
        session_expires_at=session_expires_at,
    )


@router.post("/google", response_model=GoogleAuthResponse)
def google_login(payload: GoogleLoginRequest, db: DbSession) -> GoogleAuthResponse:
    """Công khai. Bước 1 của đăng nhập bằng Google (Google Identity Services ID Token).

    * Đã có tài khoản  -> `status="AUTHENTICATED"`, kèm `tokens`.
    * Chưa có tài khoản -> `status="NEEDS_REGISTRATION"`, kèm `profile` (điền sẵn
      form) và `signup_ticket` (gửi lại ở `POST /auth/google/complete`).

    403 nếu email không thuộc tên miền Gimasys, nếu tài khoản bị khoá, hoặc nếu là
    Mentor chưa được Admin duyệt (detail bắt đầu bằng `PENDING_APPROVAL`).
    """
    result, user, identity = auth_service.google_sign_in(db, payload.credential)

    if result == auth_service.GOOGLE_AUTHENTICATED:
        return GoogleAuthResponse(status="AUTHENTICATED", tokens=_token_response(db, user))

    assigned_role, initial_status = auth_service.role_for_email(identity["email"])
    return GoogleAuthResponse(
        status="NEEDS_REGISTRATION",
        profile=GoogleProfile(
            email=identity["email"],
            full_name=identity["full_name"],
            avatar_url=identity.get("avatar_url"),
            assigned_role=assigned_role,
            needs_admin_approval=initial_status == UserStatus.PENDING,
        ),
        signup_ticket=security.create_signup_ticket(
            email=identity["email"],
            full_name=identity["full_name"],
            avatar_url=identity.get("avatar_url"),
        ),
    )


@router.post("/google/complete", response_model=GoogleAuthResponse, status_code=status.HTTP_201_CREATED)
def google_complete_signup(payload: GoogleSignupRequest, db: DbSession) -> GoogleAuthResponse:
    """Công khai (bảo vệ bằng `signup_ticket`). Bước 2: tạo tài khoản từ hồ sơ vừa nhập.

    Vai trò do tên miền email quyết định: `@edu.gimasys.com` -> INTERN dùng được
    ngay; `@gimasys.com` -> MENTOR ở trạng thái PENDING. Với Mentor, response
    KHÔNG có token — 403 `PENDING_APPROVAL` sẽ được trả khi họ thử đăng nhập lại,
    nên frontend hiện màn "chờ Admin duyệt".

    400 nếu vé hết hạn / thiếu trường bắt buộc, 409 nếu email đã có tài khoản.
    """
    user = auth_service.complete_google_signup(
        db,
        signup_ticket=payload.signup_ticket,
        full_name=payload.full_name,
        profile=payload.model_dump(
            include={"phone", "department", "university", "major", "github_url"},
            exclude_none=True,
        ),
    )

    if user.status == UserStatus.PENDING:
        return GoogleAuthResponse(
            status="NEEDS_REGISTRATION",
            profile=GoogleProfile(
                email=user.email,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                assigned_role=user.role,
                needs_admin_approval=True,
            ),
        )
    return GoogleAuthResponse(status="AUTHENTICATED", tokens=_token_response(db, user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Công khai. Đăng nhập bằng mật khẩu — **chỉ cho tài khoản ADMIN**.

    Tài khoản admin do `scripts/ensure_admin.py` tạo lúc container khởi động
    (`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`). Đây là đường vào không
    phụ thuộc Google, cần thiết vì Mentor mới phải có ADMIN duyệt.

    401 nếu sai email/mật khẩu; 403 nếu tài khoản không phải ADMIN, bị khoá, hoặc
    email ngoài tên miền cho phép.
    """
    user = auth_service.authenticate(db, payload.email, payload.password)
    return _token_response(db, user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: DbSession) -> AccessTokenResponse:
    """Public. Exchange a valid refresh token for a fresh access token."""
    access = auth_service.refresh_access_token(db, payload.refresh_token)
    return AccessTokenResponse(access_token=access, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: DbSession, current_user: CurrentUser) -> None:
    """Revoke the current refresh token."""
    auth_service.logout(db, current_user, payload.refresh_token)


@router.get("/me", response_model=MeOut)
def get_me(current_user: CurrentUser) -> MeOut:
    return current_user


@router.patch("/me", response_model=MeOut)
def update_me(payload: UserUpdate, db: DbSession, current_user: CurrentUser) -> MeOut:
    return auth_service.update_me(db, current_user, payload.model_dump(exclude_unset=True))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(db: DbSession, current_user: CurrentUser) -> None:
    """Xóa tài khoản của chính mình (xoá mềm)."""
    auth_service.delete_self(db, current_user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, db: DbSession, current_user: CurrentUser,
) -> None:
    """400 if the old password is wrong. Revokes all refresh tokens on success."""
    auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
