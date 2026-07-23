"""Model registry.

Importing this package registers every table on `Base.metadata`
(used by Alembic autogenerate and create_all). Import new models here.
"""
from app.models.assignment import AssignmentStatus, LessonProgress, RoadmapAssignment
from app.models.auth import RefreshToken
from app.models.comment import Comment
from app.models.document import Document, DocumentTag, DocumentType, Tag
from app.models.group import Group, GroupMember
from app.models.roadmap import Module, ModuleDocument, Roadmap
from app.models.user import Role, User, UserStatus

__all__ = [
    # user
    "User", "Role", "UserStatus",
    # auth
    "RefreshToken",
    # group
    "Group", "GroupMember",
    # document
    "Document", "DocumentType", "Tag", "DocumentTag",
    # roadmap
    "Roadmap", "Module", "ModuleDocument",
    # assignment
    "RoadmapAssignment", "AssignmentStatus", "LessonProgress",
    # comment
    "Comment",
]
