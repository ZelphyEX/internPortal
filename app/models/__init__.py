"""Model registry.

Importing this package registers every table on `Base.metadata`
(used by Alembic autogenerate and create_all). Import new models here.
"""
from app.models.assignment import AssignmentStatus, LessonProgress, RoadmapAssignment
from app.models.auth import RefreshToken
from app.models.comment import Comment
from app.models.daily_report import DailyReport, DailyReportStatus
from app.models.document import Document, DocumentTag, DocumentType, Tag
from app.models.enums import Department
from app.models.group import Group, GroupMember
from app.models.project import Project, ProjectMember, ProjectStatus, ProjectTag
from app.models.roadmap import LessonAttachment, Module, ModuleDocument, Roadmap
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import Role, User, UserStatus

__all__ = [
    # shared enums
    "Department",
    # user
    "User", "Role", "UserStatus",
    # auth
    "RefreshToken",
    # group
    "Group", "GroupMember",
    # document
    "Document", "DocumentType", "Tag", "DocumentTag",
    # roadmap
    "Roadmap", "Module", "ModuleDocument", "LessonAttachment",
    # assignment
    "RoadmapAssignment", "AssignmentStatus", "LessonProgress",
    # comment
    "Comment",
    # project
    "Project", "ProjectStatus", "ProjectMember", "ProjectTag",
    # task
    "Task", "TaskStatus", "TaskPriority",
    # daily report
    "DailyReport", "DailyReportStatus",
]
