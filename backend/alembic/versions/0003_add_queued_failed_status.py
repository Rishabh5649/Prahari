"""Add 'queued' and 'failed' values to circular_status enum.

Revision ID: 0003_add_queued_failed
Revises: 0002_add_rejected
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_queued_failed"
down_revision: Union[str, None] = "9aff473cd4a6_constrain_department_enum"  # Correcting based on files found
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use op.execute as Postgres doesn't support ALTER TYPE in transaction for some cases,
    # but Alembic usually handles this or we can use op.get_bind().execute(...)
    # For simplicity and reliability in Postgres:
    op.execute("ALTER TYPE circular_status ADD VALUE IF NOT EXISTS 'queued'")
    op.execute("ALTER TYPE circular_status ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    pass
