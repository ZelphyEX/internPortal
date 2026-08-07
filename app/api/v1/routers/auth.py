from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginUser,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    GoogleLoginRequest,
)
from app.models.user import Role
from app.schemas.user import MeOut, RegisterOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> RegisterOut:
    """Public. Tạo tài khoản INTERN (dùng được ngay) hoặc MENTOR (trạng thái
    PENDING, phải chờ ADMIN duyệt mới đăng nhập được). 409 nếu email đã tồn tại."""
    return auth_service.register(
        db,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        role=Role(payload.role.value),
    )



@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: DbSession) -> TokenResponse:
    """Xác thực đăng nhập hoặc đăng ký bằng Google Identity Services credential (ID Token)."""
    user = auth_service.google_authenticate(db, payload.credential)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        user=LoginUser.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Public. 401 on bad credentials, 403 if the account is LOCKED."""
    user = auth_service.authenticate(db, payload.email, payload.password)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        user=LoginUser.model_validate(user),
    )


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
