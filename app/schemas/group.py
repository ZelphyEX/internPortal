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


class AddMembersResult(BaseModel):
    """Kết quả thêm thành viên — kèm số lộ trình/dự án người mới **kế thừa** từ nhóm.

    Gán nhóm là luật thường trực: vào nhóm là nhận ngay mọi lộ trình và dự án nhóm
    đang có. Frontend dùng các số này để báo cho Mentor biết đã xảy ra chuyện gì.
    """
    members: list[GroupMemberOut] = []
    added_count: int = 0
    skipped_existing: int = 0
    inherited_roadmaps: int = 0
    inherited_projects: int = 0


class RemoveMemberResult(BaseModel):
    """Kết quả gỡ thành viên.

    `kept_*` là số lộ trình/dự án KHÔNG bị thu hồi vì người đó đã có tiến độ (đã học
    bài / đang có task) — chúng được chuyển thành gán cá nhân thay vì xoá.
    """
    revoked_roadmaps: int = 0
    kept_roadmaps: int = 0
    revoked_projects: int = 0
    kept_projects: int = 0


class AddGroupToProjectRequest(BaseModel):
    """Gán cả một nhóm vào dự án."""
    group_id: int


class AddGroupResult(BaseModel):
    added_count: int = 0
    skipped_existing: int = 0
