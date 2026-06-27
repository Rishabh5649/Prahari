"""MAPs API router — list, detail, approve, and reject MAP items."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.map_item import MapItem
from app.schemas.maps import (
    ApproveRequest,
    EvidenceBrief,
    JudgmentBrief,
    MapDetailResponse,
    MapItemResponse,
    RejectRequest,
)

router = APIRouter(prefix="/api/maps", tags=["MAPs"])


def _map_to_response(m: MapItem) -> MapItemResponse:
    """Convert a MapItem ORM object to a response schema."""
    return MapItemResponse(
        id=str(m.id),
        circular_id=str(m.circular_id),
        parent_map_id=str(m.parent_map_id) if m.parent_map_id else None,
        what=m.what,
        deadline=m.deadline,
        department=m.department,
        evidence_type=m.evidence_type,
        confidence_score=m.confidence_score,
        status=m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
        circular_title=m.circular.title if m.circular else None,
        circular_source_url=m.circular.source_url if m.circular else None,
    )


@router.get("", response_model=list[MapItemResponse])
async def list_maps(
    circular_id: UUID | None = Query(None, description="Filter by circular UUID"),
    department: str | None = Query(None, description="Filter by department"),
    status: str | None = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    """List all MAP items with optional filters."""
    query = select(MapItem).options(joinedload(MapItem.circular))

    if circular_id:
        query = query.where(MapItem.circular_id == circular_id)
    if department:
        query = query.where(MapItem.department == department)
    if status:
        query = query.where(MapItem.status == status)

    query = query.order_by(MapItem.deadline.asc())
    result = await db.execute(query)
    maps = result.scalars().all()

    return [_map_to_response(m) for m in maps]


@router.get("/{map_id}", response_model=MapDetailResponse)
async def get_map_detail(
    map_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single MAP with its evidence submissions, judgments, and children."""
    result = await db.execute(
        select(MapItem)
        .where(MapItem.id == map_id)
        .options(
            joinedload(MapItem.circular),
            selectinload(MapItem.evidence_submissions),
            selectinload(MapItem.judgments),
            selectinload(MapItem.children),
        )
    )
    map_item = result.scalar_one_or_none()

    if map_item is None:
        raise HTTPException(status_code=404, detail="MAP item not found")

    return MapDetailResponse(
        id=str(map_item.id),
        circular_id=str(map_item.circular_id),
        parent_map_id=str(map_item.parent_map_id) if map_item.parent_map_id else None,
        what=map_item.what,
        deadline=map_item.deadline,
        department=map_item.department,
        evidence_type=map_item.evidence_type,
        confidence_score=map_item.confidence_score,
        status=map_item.status,
        created_at=map_item.created_at,
        updated_at=map_item.updated_at,
        circular_title=map_item.circular.title if map_item.circular else None,
        circular_source_url=map_item.circular.source_url if map_item.circular else None,
        evidence_submissions=[
            EvidenceBrief(
                id=str(e.id),
                file_name=e.file_name,
                submitted_by=e.submitted_by,
                submitted_at=e.submitted_at,
            )
            for e in map_item.evidence_submissions
        ],
        judgments=[
            JudgmentBrief(
                id=str(j.id),
                verdict=j.verdict,
                reasoning=j.reasoning,
                human_override=j.human_override,
                judged_at=j.judged_at,
            )
            for j in sorted(map_item.judgments, key=lambda x: x.judged_at, reverse=True)
        ],
        children=[_map_to_response(c) for c in map_item.children],
    )


@router.patch("/{map_id}/approve", response_model=MapItemResponse)
async def approve_map(
    map_id: UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human-approve a pending_review MAP, setting its status to 'assigned'."""
    result = await db.execute(select(MapItem).where(MapItem.id == map_id))
    map_item = result.scalar_one_or_none()

    if map_item is None:
        raise HTTPException(status_code=404, detail="MAP item not found")
    if map_item.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: MAP status is '{map_item.status}', expected 'pending_review'",
        )

    map_item.status = "assigned"
    await db.flush()

    audit = AuditLog(
        event_type="map_approved",
        entity_type="map_item",
        entity_id=str(map_item.id),
        payload={
            "approved_by": body.approved_by,
            "department": map_item.department,
        },
        actor=body.approved_by,
    )
    db.add(audit)

    # Cascade approval to child MAPs if split
    result_children = await db.execute(
        select(MapItem).where(MapItem.parent_map_id == map_item.id)
    )
    children = result_children.scalars().all()
    for child in children:
        if child.status == "pending_review":
            child.status = "assigned"
            audit_child = AuditLog(
                event_type="map_approved",
                entity_type="map_item",
                entity_id=str(child.id),
                payload={
                    "approved_by": body.approved_by,
                    "department": child.department,
                    "cascaded_from_parent": str(map_item.id),
                },
                actor=body.approved_by,
            )
            db.add(audit_child)

    await db.flush()
    await db.refresh(map_item)

    return _map_to_response(map_item)


@router.patch("/{map_id}/reject", response_model=MapItemResponse)
async def reject_map(
    map_id: UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human-reject a MAP, setting its status to 'rejected'."""
    result = await db.execute(select(MapItem).where(MapItem.id == map_id))
    map_item = result.scalar_one_or_none()

    if map_item is None:
        raise HTTPException(status_code=404, detail="MAP item not found")
    if map_item.status not in ("pending_review", "assigned"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject: MAP status is '{map_item.status}'",
        )

    map_item.status = "rejected"
    await db.flush()

    audit = AuditLog(
        event_type="map_rejected",
        entity_type="map_item",
        entity_id=str(map_item.id),
        payload={
            "rejected_by": body.rejected_by,
            "reason": body.reason,
            "department": map_item.department,
        },
        actor=body.rejected_by,
    )
    db.add(audit)

    # Cascade rejection to child MAPs if split
    result_children = await db.execute(
        select(MapItem).where(MapItem.parent_map_id == map_item.id)
    )
    children = result_children.scalars().all()
    for child in children:
        if child.status in ("pending_review", "assigned"):
            child.status = "rejected"
            audit_child = AuditLog(
                event_type="map_rejected",
                entity_type="map_item",
                entity_id=str(child.id),
                payload={
                    "rejected_by": body.rejected_by,
                    "reason": f"Cascaded rejection from parent. Parent reason: {body.reason}",
                    "department": child.department,
                    "cascaded_from_parent": str(map_item.id),
                },
                actor=body.rejected_by,
            )
            db.add(audit_child)

    await db.flush()
    await db.refresh(map_item)

    return _map_to_response(map_item)


# ---------------------------------------------------------------------------
# Status-update endpoint — recalculates parent MAP / circular status
# ---------------------------------------------------------------------------

from app.models.circular import Circular
from pydantic import BaseModel as _BaseModel


class StatusUpdateRequest(_BaseModel):
    """Internal status update that triggers parent recalculation."""

    actor: str = "system"


@router.patch("/{map_id}/status-update", response_model=MapItemResponse)
async def update_map_status(
    map_id: UUID,
    body: StatusUpdateRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recalculate the status of the parent MAP (if any) and the parent circular
    after a child MAP status changes.

    Called internally by the judge agent and override flow.
    """
    result = await db.execute(select(MapItem).where(MapItem.id == map_id))
    map_item = result.scalar_one_or_none()

    if map_item is None:
        raise HTTPException(status_code=404, detail="MAP item not found")

    # Recalculate parent MAP if this is a child
    if map_item.parent_map_id:
        siblings_result = await db.execute(
            select(MapItem).where(MapItem.parent_map_id == map_item.parent_map_id)
        )
        siblings = list(siblings_result.scalars().all())

        all_satisfied = all(s.status == "satisfied" for s in siblings)
        any_overdue = any(s.status == "overdue" for s in siblings)

        parent_result = await db.execute(
            select(MapItem).where(MapItem.id == map_item.parent_map_id)
        )
        parent = parent_result.scalar_one_or_none()

        if parent:
            if all_satisfied:
                parent.status = "satisfied"
            elif any_overdue:
                parent.status = "overdue"
            else:
                parent.status = "in_progress"

    # Recalculate circular status
    circ_result = await db.execute(
        select(MapItem).where(MapItem.circular_id == map_item.circular_id)
    )
    all_maps = list(circ_result.scalars().all())

    if all_maps:
        all_satisfied = all(m.status in ("satisfied", "rejected") for m in all_maps)
        any_overdue = any(m.status == "overdue" for m in all_maps)

        circ = await db.get(Circular, map_item.circular_id)
        if circ:
            if all_satisfied:
                circ.status = "compliant"
            elif any_overdue:
                circ.status = "overdue"
            else:
                circ.status = "in_progress"

    await db.flush()
    await db.refresh(map_item)

    return _map_to_response(map_item)

