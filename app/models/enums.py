"""Enums shared by more than one table.

`Department` is used by `modules.track` and `projects.department`, so the
PostgreSQL type `department` is created once and the same SQLAlchemy type object
is reused by both columns.

`users.department` used to be a third one — dropped in migration `f1c6b83ad74e`
(no form ever set it, so every real account was NULL). The PG type itself was
kept, since the two columns above still need it.
"""
import enum

from sqlalchemy import Enum as SAEnum


class Department(str, enum.Enum):
    """Technical track of a roadmap module / a project.

    The values are the exact labels the frontend displays (agreed in
    docs/backend-requirements.md mục 1), so no mapping layer is needed.
    """
    JAVA_BACKEND = "Java Back-End"
    REACT_FRONTEND = "React Front-End"
    CLOUD_DEVOPS = "Cloud & DevOps"
    SALESFORCE_ERP = "Salesforce/ERP"
    AI_DATA_SCIENCE = "AI & Data Science"


def pg_enum(py_enum: type[enum.Enum], name: str) -> SAEnum:
    """Build a native PG enum that stores the member *values* (not the names)."""
    return SAEnum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


# One shared type object -> one CREATE TYPE for both columns.
DEPARTMENT_ENUM = pg_enum(Department, "department")
