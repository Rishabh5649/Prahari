"""Evidence service — file upload to MinIO, department queries, overdue escalation."""

import io
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.minio_client import minio_client
from app.models.audit_log import AuditLog
from app.models.evidence import EvidenceSubmission
from app.models.map_item import MapItem
from app.utils.hashing import hash_content

logger = logging.getLogger(__name__)


async def submit_evidence(
    map_id: UUID,
    file_name: str,
    file_data: bytes,
    submitted_by: str,
    db: AsyncSession,
) -> EvidenceSubmission:
    """Upload evidence to MinIO and record it against a MAP.

    Args:
        map_id: The UUID of the MAP item.
        file_name: Original file name.
        file_data: Raw file bytes.
        submitted_by: Name or email of the submitting officer.
        db: Async database session.

    Returns:
        The persisted EvidenceSubmission ORM object.

    Raises:
        HTTPException: If the MAP does not exist or is not in 'assigned' status.
    """
    # Validate MAP exists and is in the right status
    result = await db.execute(select(MapItem).where(MapItem.id == map_id))
    map_item = result.scalar_one_or_none()

    if map_item is None:
        raise HTTPException(status_code=404, detail="MAP item not found")
    if map_item.status != "assigned":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot submit evidence: MAP status is '{map_item.status}', "
                "expected 'assigned'"
            ),
        )

    # Generate MinIO object key
    object_key = f"evidence/{map_id}/{uuid4()}/{file_name}"

    # Upload to MinIO
    import asyncio
    data_stream = io.BytesIO(file_data)
    await asyncio.to_thread(
        minio_client.put_object,
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        data=data_stream,
        length=len(file_data),
    )

    # Persist evidence submission
    evidence = EvidenceSubmission(
        map_id=map_id,
        file_name=file_name,
        minio_object_key=object_key,
        submitted_by=submitted_by,
    )
    db.add(evidence)

    # Update MAP status
    map_item.status = "evidence_submitted"

    await db.flush()

    # Audit log
    audit = AuditLog(
        event_type="evidence_submitted",
        entity_type="map_item",
        entity_id=str(map_id),
        payload={
            "evidence_id": str(evidence.id),
            "file_name": file_name,
            "submitted_by": submitted_by,
            "minio_key": object_key,
        },
        input_hash=hash_content(file_data.hex()),
        actor=submitted_by,
    )
    db.add(audit)
    await db.flush()

    return evidence


async def get_maps_for_department(
    department: str, db: AsyncSession
) -> list[MapItem]:
    """Return all non-satisfied and non-split MAPs for a department, ordered by deadline."""
    parent_ids_subq = select(MapItem.parent_map_id).where(MapItem.parent_map_id.is_not(None))
    result = await db.execute(
        select(MapItem)
        .where(MapItem.department == department)
        .where(MapItem.status != "satisfied")
        .where(MapItem.id.notin_(parent_ids_subq))
        .order_by(MapItem.deadline.asc())
    )
    return list(result.scalars().all())


async def check_and_escalate_overdue(db: AsyncSession) -> int:
    """Find overdue MAPs and escalate their status.

    A MAP is overdue if its deadline has passed, its status is one of:
    'assigned', 'evidence_submitted', or 'partial', and it is not a split parent MAP.

    Returns:
        The number of MAPs escalated.
    """
    now = datetime.now(timezone.utc)
    escalatable = ("assigned", "evidence_submitted", "partial")
    parent_ids_subq = select(MapItem.parent_map_id).where(MapItem.parent_map_id.is_not(None))

    result = await db.execute(
        select(MapItem).where(
            MapItem.deadline < now,
            MapItem.status.in_(escalatable),
            MapItem.id.notin_(parent_ids_subq),
        )
    )
    overdue_maps = list(result.scalars().all())

    for map_item in overdue_maps:
        prev_status = map_item.status
        map_item.status = "overdue"

        audit = AuditLog(
            event_type="map_escalated_overdue",
            entity_type="map_item",
            entity_id=str(map_item.id),
            payload={
                "previous_status": prev_status,
                "deadline": map_item.deadline.isoformat(),
                "department": map_item.department,
            },
            actor="system",
        )
        db.add(audit)

    if overdue_maps:
        await db.flush()
        logger.info("Escalated %d MAP(s) to overdue status", len(overdue_maps))

    return len(overdue_maps)
