"""User output/update schemas (shared by auth; extended by Dev B for /users)."""
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, UserStatus


class RegisterOut(BaseModel):
    """POST /auth/register response (no avatar per spec)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: Role
    status: UserStatus


class MeOut(BaseModel):
    """GET/PATCH /auth/me response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: Role
    status: UserStatus
    avatar_url: str | None = None


class UserUpdate(BaseModel):
    """PATCH /auth/me request — only provided fields are updated."""
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)


# --------------------------------------------------------------------------- #
# User management (Dev B — API_SPEC mục 3)
# --------------------------------------------------------------------------- #
class UserProfileFields(BaseModel):
    """Intern profile fields (backend-requirements mục 1).

    Every field is optional and only meaningful for `role=INTERN`.

    Đã bỏ hẳn khỏi bảng `users`: `phone`, `university`, `mentor_id`, `start_date`,
    `end_date` (migration d5c8a2e64f19), `major` (e7a4b1d09c53) và `department` —
    Khối kỹ thuật (f1c6b83ad74e).
    """
    model_config = ConfigDict(from_attributes=True)

    bio: str | None = None
    github_url: str | None = None
    score: float | None = None
    attendance_rate: float | None = None


class UserListItem(UserProfileFields):
    """GET /users list item."""

    id: int
    full_name: str
    # `str` (not EmailStr) on purpose: this value comes from the DB and was
    # already validated on write. Re-validating on OUTPUT would 500 the whole
    # list if a single legacy row has an odd domain (e.g. reserved ".test").
    email: str
    role: Role
    status: UserStatus
    avatar_url: str | None = None


class UserOut(UserProfileFields):
    """GET /users/{id} detail + create/lock/unlock response."""

    id: int
    full_name: str
    email: str  # see UserListItem.email — response side, not re-validated
    role: Role
    status: UserStatus
    avatar_url: str | None = None


class UserProfileUpdate(BaseModel):
    """PATCH /users/{id}/profile request (MENTOR/ADMIN).

    Only the fields present in the payload change; sending an explicit `null`
    clears that field. Kept separate from `PATCH /auth/me`, which is how a user
    edits their *own* name/avatar.
    """
    bio: str | None = None
    github_url: str | None = Field(default=None, max_length=512)
    score: float | None = Field(default=None, ge=0, le=100)
    attendance_rate: float | None = Field(default=None, ge=0, le=100)


class UserRoleUpdate(BaseModel):
    """PATCH /users/{id}/role request (ADMIN).

    Chỉ nhận `INTERN` hoặc `MENTOR` — service từ chối mọi giá trị khác, kể cả
    `ADMIN` (vai trò Quản trị viên không cấp qua API).
    """
    role: Role


class UserCreate(BaseModel):
    """POST /users request.

    MENTOR chỉ tạo được `INTERN`; ADMIN tạo được `INTERN` hoặc `MENTOR`.
    Không tạo được tài khoản ADMIN qua API (dùng `scripts/create_user.py`).
    """
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Role = Role.INTERN
