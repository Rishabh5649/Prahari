"""Evidence Submission ORM model."""

import uuid

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EvidenceSubmission(Base):
    """An evidence file uploaded against a MAP item."""

    __tablename__ = "evidence_submissions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("map_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = Column(Text, nullable=False)
    minio_object_key = Column(Text, nullable=False)
    submitted_by = Column(
        Text, nullable=False, comment="Department officer name/email"
    )
    submitted_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    map_item = relationship("MapItem", backref="evidence_submissions", lazy="selectin")
