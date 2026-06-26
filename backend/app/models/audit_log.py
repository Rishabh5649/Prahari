"""Audit Log ORM model — immutable, append-only event ledger."""

from sqlalchemy import BigInteger, Column, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    """Append-only audit trail.

    Protected by PostgreSQL rules that prevent UPDATE and DELETE.
    See Alembic migration for the enforcement triggers.
    """

    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(
        Text,
        nullable=False,
        comment="e.g. circular_ingested, map_extracted, judgment_made",
    )
    entity_type = Column(
        Text,
        nullable=False,
        comment="e.g. circular, map_item, evidence, judgment",
    )
    entity_id = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, comment="Full input/output snapshot")
    input_hash = Column(Text, nullable=True, comment="SHA-256 of input")
    output_hash = Column(Text, nullable=True, comment="SHA-256 of output")
    model_version = Column(Text, nullable=True, comment="e.g. claude-sonnet-4-6")
    actor = Column(Text, nullable=True, comment="User email or 'system'")
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
