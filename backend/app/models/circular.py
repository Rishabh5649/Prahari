"""Circular ORM model — ingested regulatory documents."""

import uuid

from sqlalchemy import Column, Enum, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class CircularStatus(str):
    PROCESSING = "processing"
    IN_PROGRESS = "in_progress"
    COMPLIANT = "compliant"
    OVERDUE = "overdue"


CIRCULAR_STATUS_ENUM = Enum(
    "processing", "in_progress", "compliant", "overdue",
    name="circular_status",
    create_constraint=True,
)


class Circular(Base):
    """Represents an ingested RBI/SEBI/DPDP regulatory circular."""

    __tablename__ = "circulars"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    source_url = Column(Text, nullable=True)
    source_hash = Column(Text, nullable=False, comment="SHA-256 of raw content")
    raw_text = Column(Text, nullable=False)
    status = Column(
        CIRCULAR_STATUS_ENUM,
        nullable=False,
        default="processing",
        server_default="processing",
    )
    ingested_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    title = Column(Text, nullable=True, comment="Extracted from document")
