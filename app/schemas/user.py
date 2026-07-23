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
