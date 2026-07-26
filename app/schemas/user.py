"""User output/update schemas (shared by auth; extended by Dev B for /users)."""
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Department
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
    `mentor_name`/`mentor_email` are resolved from `mentor_id` by the service.
    """
    model_config = ConfigDict(from_attributes=True)

    department: Department | None = None
    mentor_id: int | None = None
    mentor_name: str | None = None
    mentor_email: str | None = None
    phone: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    university: str | None = None
    major: str | None = None
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
    department: Department | None = None
    mentor_id: int | None = None
    phone: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    university: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    github_url: str | None = Field(default=None, max_length=512)
    score: float | None = Field(default=None, ge=0, le=100)
    attendance_rate: float | None = Field(default=None, ge=0, le=100)


class UserCreate(BaseModel):
    """POST /users request (ADMIN creates MENTOR/ADMIN accounts)."""
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Role = Role.MENTOR
