"""add mode to exam_attempts

Revision ID: b3f19c90f2d8
Revises: a4e19f70c2b8
Create Date: 2026-08-11 12:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f19c90f2d8'
down_revision: Union[str, None] = 'a4e19f70c2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'exam_attempts',
        sa.Column('mode', sa.String(length=50), nullable=False, server_default='exam')
    )


def downgrade() -> None:
    op.drop_column('exam_attempts', 'mode')
