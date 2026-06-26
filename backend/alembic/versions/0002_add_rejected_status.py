"""Add 'rejected' value to map_status enum.

Revision ID: 0002_add_rejected
Revises: 0001_initial
Create Date: 2025-06-21
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_rejected"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE map_status ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # A full recreation of the enum would be needed, which is not safe
    # to do in a downgrade.  This is a no-op.
    pass
