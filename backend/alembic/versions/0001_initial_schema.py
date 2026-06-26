"""Initial schema — all tables and audit log protection rules.

Revision ID: 0001_initial
Revises: None
Create Date: 2025-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUM types ---
    circular_status = sa.Enum(
        "processing", "in_progress", "compliant", "overdue",
        name="circular_status",
    )
    map_status = sa.Enum(
        "pending_review", "assigned", "evidence_submitted", "judging",
        "satisfied", "partial", "insufficient", "overdue",
        name="map_status",
    )
    verdict_enum = sa.Enum(
        "satisfied", "partial", "insufficient",
        name="verdict",
    )

    # --- circulars ---
    op.create_table(
        "circulars",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", circular_status, nullable=False, server_default="processing"),
        sa.Column("ingested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("title", sa.Text(), nullable=True),
    )

    # --- map_items ---
    op.create_table(
        "map_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("circular_id", UUID(as_uuid=True), sa.ForeignKey("circulars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_map_id", UUID(as_uuid=True), sa.ForeignKey("map_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("what", sa.Text(), nullable=False),
        sa.Column("deadline", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", map_status, nullable=False, server_default="pending_review"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )

    # --- evidence_submissions ---
    op.create_table(
        "evidence_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("map_id", UUID(as_uuid=True), sa.ForeignKey("map_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("minio_object_key", sa.Text(), nullable=False),
        sa.Column("submitted_by", sa.Text(), nullable=False),
        sa.Column("submitted_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- judgments ---
    op.create_table(
        "judgments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("map_id", UUID(as_uuid=True), sa.ForeignKey("map_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", UUID(as_uuid=True), sa.ForeignKey("evidence_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verdict", verdict_enum, nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("human_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("override_by", sa.Text(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("judged_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("output_hash", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Immutability rules for audit_log ---
    op.execute(
        "CREATE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING;"
    )
    op.execute(
        "CREATE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;"
    )


def downgrade() -> None:
    # Drop rules first
    op.execute("DROP RULE IF EXISTS no_delete_audit ON audit_log;")
    op.execute("DROP RULE IF EXISTS no_update_audit ON audit_log;")

    op.drop_table("audit_log")
    op.drop_table("judgments")
    op.drop_table("evidence_submissions")
    op.drop_table("map_items")
    op.drop_table("circulars")

    # Drop ENUM types
    sa.Enum(name="verdict").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="map_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="circular_status").drop(op.get_bind(), checkfirst=True)
