"""SQLAlchemy 2.0 declarative base.

All ORM models inherit from `Base` (import it from here).
Model modules are aggregated in `app.models.__init__` so that
`import app.models` registers every table on `Base.metadata`
(used by Alembic autogenerate and `create_all`).
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
