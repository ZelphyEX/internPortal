"""Group + membership schemas (API_SPEC mục 4)."""
from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cohort: str | None = Field(default=None, max_length=100)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    cohort: str | None = Field(default=None, max_length=100)
    description: str | None = None


class GroupOut(BaseModel):
    """List item — includes a member count."""
    id: int
    name: str
    cohort: str | None = None
    description: str | None = None
    member_count: int = 0


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str  # response side — not re-validated (see schemas/user.py)


class GroupDetailOut(BaseModel):
    """Detail — includes the member list."""
    id: int
    name: str
    cohort: str | None = None
    description: str | None = None
    members: list[GroupMemberOut] = []


class AddMembersRequest(BaseModel):
    """Bulk add. Duplicates (already in the group) and unknown ids are skipped."""
    user_ids: list[int] = Field(min_length=1)
