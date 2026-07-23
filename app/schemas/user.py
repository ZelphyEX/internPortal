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
class UserListItem(BaseModel):
    """GET /users list item."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    # `str` (not EmailStr) on purpose: this value comes from the DB and was
    # already validated on write. Re-validating on OUTPUT would 500 the whole
    # list if a single legacy row has an odd domain (e.g. reserved ".test").
    email: str
    role: Role
    status: UserStatus


class UserOut(BaseModel):
    """GET /users/{id} detail + create/lock/unlock response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str  # see UserListItem.email — response side, not re-validated
    role: Role
    status: UserStatus
    avatar_url: str | None = None


class UserCreate(BaseModel):
    """POST /users request (ADMIN creates MENTOR/ADMIN accounts)."""
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Role = Role.MENTOR
