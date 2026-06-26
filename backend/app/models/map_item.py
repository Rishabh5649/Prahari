"""MAP Item ORM model — Mandatory Action Points extracted from circulars."""

import uuid

from sqlalchemy import Column, Enum, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


MAP_STATUS_ENUM = Enum(
    "pending_review",
    "assigned",
    "evidence_submitted",
    "judging",
    "satisfied",
    "partial",
    "insufficient",
    "overdue",
    "rejected",
    name="map_status",
    create_constraint=True,
)

DEPARTMENTS = (
    "IT-Security",
    "KYC/AML",
    "Retail Banking",
    "Treasury",
    "Legal",
    "Risk",
)

DEPARTMENT_ENUM = Enum(
    *DEPARTMENTS,
    name="department_enum",
    create_constraint=True,
)


class MapItem(Base):
    """A single Mandatory Action Point extracted from a circular."""

    __tablename__ = "map_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    circular_id = Column(
        UUID(as_uuid=True),
        ForeignKey("circulars.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("map_items.id", ondelete="SET NULL"),
        nullable=True,
        comment="For child MAPs created by splitting",
    )
    what = Column(Text, nullable=False, comment="What action must be done")
    deadline = Column(TIMESTAMP(timezone=True), nullable=False)
    department = Column(DEPARTMENT_ENUM, nullable=False, comment="Routed department")
    evidence_type = Column(
        Text, nullable=False, comment="Expected evidence description"
    )
    confidence_score = Column(Float, nullable=False)
    status = Column(
        MAP_STATUS_ENUM,
        nullable=False,
        default="pending_review",
        server_default="pending_review",
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    # Relationships
    circular = relationship("Circular", backref="map_items", lazy="selectin")
    parent = relationship(
        "MapItem", remote_side="MapItem.id", backref="children", lazy="selectin"
    )
