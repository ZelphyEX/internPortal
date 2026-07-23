"""Shared schemas — pagination envelope."""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard pagination response: { items, total, page, size, pages }."""
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
