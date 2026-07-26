"""Pagination helper shared by all list endpoints (Dev B: reuse this).

Usage:
    @router.get("")
    def list_docs(db: DbSession, page: PageQuery = DEFAULT_PAGE, size: SizeQuery = DEFAULT_SIZE):
        stmt = select(Document).where(...).order_by(Document.created_at.desc())
        rows, total, pages = paginate(db, stmt, page=page, size=size)
        return Page(items=[...], total=total, page=page, size=size, pages=pages)
"""
from math import ceil
from typing import Annotated

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

DEFAULT_PAGE = 1
DEFAULT_SIZE = 20
MAX_SIZE = 100

# Shared query params so every list endpoint documents the same bounds in
# Swagger (the `size` cap used to be visible only as a schema `maximum`, which
# clients had to discover by triggering a 422).
PageQuery = Annotated[
    int, Query(ge=1, description=f"1-based page number (default {DEFAULT_PAGE}).")
]
SizeQuery = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_SIZE,
        description=(
            f"Items per page, {1}..{MAX_SIZE} (default {DEFAULT_SIZE}). "
            f"A value above {MAX_SIZE} is rejected with 422."
        ),
    ),
]


def paginate(db: Session, stmt: Select, *, page: int, size: int):
    """Return (rows, total, pages) for `stmt` at the given page/size."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.limit(size).offset((page - 1) * size)).all()
    pages = ceil(total / size) if size else 0
    return rows, total, pages
