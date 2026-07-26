"""Reusable declarative mixins for timestamp columns (TIMESTAMPTZ, UTC)."""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAtMixin:
    """Adds a `created_at` column (set once on insert)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Adds `created_at` + `updated_at` (touched on every update)."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
