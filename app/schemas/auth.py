"""Auth request/response schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, UserStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    credential: str


class LoginUser(BaseModel):
    """Compact user info embedded in the login response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    # `str` (không phải EmailStr): giá trị đến từ DB và đã được kiểm lúc ghi.
    # Kiểm lại ở chiều ra sẽ làm 500 cả response nếu có dòng dữ liệu cũ lạ.
    email: str
    role: Role
    status: UserStatus = UserStatus.ACTIVE
    avatar_url: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: LoginUser
    #: Mốc reset phiên hằng ngày (ISO 8601 UTC) — mặc định 00:00 giờ Việt Nam,
    #: nên MỌI phiên cùng hết hạn tại một mốc trong ngày bất kể đăng nhập lúc nào
    #: (đăng nhập 23:50 thì phiên chỉ còn 10 phút — đúng ý đồ, không phải lỗi).
    #: `/auth/refresh` không đẩy mốc này ra xa. Client dùng nó để tự đăng xuất,
    #: không đợi request lỗi mới biết.
    session_expires_at: datetime


# --------------------------------------------------------------------------- #
# Đăng nhập bằng Google (2 bước: xác thực -> nếu chưa có tài khoản thì điền hồ sơ)
# --------------------------------------------------------------------------- #
class GoogleProfile(BaseModel):
    """Thông tin Google trả về, dùng để điền sẵn form đăng ký."""
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    #: Vai trò sẽ được cấp nếu đăng ký tiếp. Hiện luôn là INTERN — muốn lên MENTOR
    #: thì gửi yêu cầu chuyển vai trò sau khi vào portal (mục 3b).
    assigned_role: Role
    #: True nếu tài khoản tạo ra phải chờ Admin duyệt. Với luồng hiện tại luôn False;
    #: giữ lại để client xử lý được nếu chính sách đổi.
    needs_admin_approval: bool = False


class GoogleAuthResponse(BaseModel):
    """Kết quả `POST /auth/google`.

      * `AUTHENTICATED`       -> `tokens` có giá trị, đăng nhập xong.
      * `NEEDS_REGISTRATION`  -> `profile` + `signup_ticket` có giá trị; gọi tiếp
                                 `POST /auth/google/complete` để tạo tài khoản.
    """
    status: Literal["AUTHENTICATED", "NEEDS_REGISTRATION"]
    tokens: TokenResponse | None = None
    profile: GoogleProfile | None = None
    signup_ticket: str | None = None


class GoogleSignupRequest(BaseModel):
    """`POST /auth/google/complete` — tạo tài khoản mới.

    Chỉ cần **họ tên** (đã điền sẵn từ Google, người dùng sửa được). Các thông tin
    hồ sơ khác (SĐT, trường, ngành, đơn vị, GitHub) KHÔNG hỏi lúc đăng ký nữa —
    Mentor bổ sung sau qua `PATCH /users/{id}/profile`, hoặc chủ tài khoản tự sửa
    tên/ảnh qua `PATCH /auth/me`.

    Email KHÔNG nằm trong body: nó được lấy từ `signup_ticket` mà server đã ký
    sau khi Google xác thực, nên không ai đăng ký hộ email người khác được.
    """
    signup_ticket: str
    full_name: str = Field(min_length=2, max_length=255)


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
