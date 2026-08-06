"""Auth request/response schemas."""
import enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, UserStatus


class RegisterRole(str, enum.Enum):
    """Vai trò được phép tự đăng ký. KHÔNG cho đăng ký ADMIN."""
    INTERN = "INTERN"
    MENTOR = "MENTOR"


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    # INTERN -> dùng được ngay (ACTIVE).
    # MENTOR -> tạo ở trạng thái PENDING, phải chờ ADMIN duyệt mới đăng nhập được.
    role: RegisterRole = RegisterRole.INTERN


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginUser(BaseModel):
    """Compact user info embedded in the login response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: Role
    status: UserStatus = UserStatus.ACTIVE
    avatar_url: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: LoginUser


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
