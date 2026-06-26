"""Judgment ORM model — LLM verdicts on evidence."""

import uuid

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


VERDICT_ENUM = Enum(
    "satisfied", "partial", "insufficient",
    name="verdict",
    create_constraint=True,
)


class Judgment(Base):
    """An LLM-generated (or human-overridden) verdict on submitted evidence."""

    __tablename__ = "judgments"

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
    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict = Column(VERDICT_ENUM, nullable=False)
    reasoning = Column(Text, nullable=False)
    human_override = Column(Boolean, nullable=False, default=False, server_default="false")
    override_by = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)
    judged_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    map_item = relationship("MapItem", backref="judgments", lazy="selectin")
    evidence = relationship("EvidenceSubmission", backref="judgments", lazy="selectin")
