"""Pagination helper shared by all list endpoints (Dev B: reuse this).

Usage:
    stmt = select(Document).where(...).order_by(Document.created_at.desc())
    rows, total, pages = paginate(db, stmt, page=page, size=size)
    return Page(items=[...], total=total, page=page, size=size, pages=pages)
"""
from math import ceil

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

# Bounds enforced by routers via Query(ge=..., le=...); constants shared here.
DEFAULT_PAGE = 1
DEFAULT_SIZE = 20
MAX_SIZE = 100


def paginate(db: Session, stmt: Select, *, page: int, size: int):
    """Return (rows, total, pages) for `stmt` at the given page/size."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.limit(size).offset((page - 1) * size)).all()
    pages = ceil(total / size) if size else 0
    return rows, total, pages
