"""Dashboard API endpoints for the Prahari compliance-tracking system.

Provides aggregated views of circulars, MAP items, department drill-downs,
and system-wide statistics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.circular import Circular
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment
from app.models.map_item import MapItem, DEPARTMENTS
from app.schemas.dashboard import (
    ChildMapBrief,
    CircularDetailResponse,
    CircularSummary,
    LatestEvidenceBrief,
    LatestJudgmentBrief,
    MapDetail,
    SystemStats,
)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IN_PROGRESS_STATUSES = (
    "assigned",
    "evidence_submitted",
    "judging",
    "partial",
    "insufficient",
)


def _build_latest_judgment(judgments: list[Judgment]) -> LatestJudgmentBrief | None:
    """Return a brief of the most recent judgment, or None."""
    if not judgments:
        return None
    latest = max(judgments, key=lambda j: j.judged_at)
    return LatestJudgmentBrief(
        verdict=latest.verdict,
        reasoning=latest.reasoning,
        human_override=latest.human_override,
        judged_at=latest.judged_at,
    )


def _build_latest_evidence(
    submissions: list[EvidenceSubmission],
) -> LatestEvidenceBrief | None:
    """Return a brief of the most recent evidence submission, or None."""
    if not submissions:
        return None
    latest = max(submissions, key=lambda e: e.submitted_at)
    return LatestEvidenceBrief(
        file_name=latest.file_name,
        submitted_by=latest.submitted_by,
        submitted_at=latest.submitted_at,
    )


def _build_map_detail(
    map_item: MapItem,
    *,
    include_children: bool = True,
) -> MapDetail:
    """Convert a MapItem ORM instance into a MapDetail schema."""
    children: list[ChildMapBrief] = []
    if include_children and map_item.children:
        children = [
            ChildMapBrief(
                id=str(c.id),
                department=c.department,
                status=c.status,
            )
            for c in map_item.children
        ]

    return MapDetail(
        id=str(map_item.id),
        parent_map_id=str(map_item.parent_map_id) if map_item.parent_map_id else None,
        what=map_item.what,
        deadline=map_item.deadline,
        department=map_item.department,
        confidence_score=map_item.confidence_score,
        status=map_item.status,
        children=children,
        latest_judgment=_build_latest_judgment(map_item.judgments),
        latest_evidence=_build_latest_evidence(map_item.evidence_submissions),
    )


# ---------------------------------------------------------------------------
# 1. GET /circulars
# ---------------------------------------------------------------------------


@router.get("/circulars", response_model=list[CircularSummary])
async def list_circulars(db: AsyncSession = Depends(get_db)) -> list[CircularSummary]:
    """Return every circular with aggregated MAP statistics.

    Uses a single grouped aggregation query on MapItem to avoid N+1 issues.
    """
    # --- Fetch all circulars -------------------------------------------------
    circulars_result = await db.execute(
        select(Circular).order_by(Circular.ingested_at.desc())
    )
    circulars: list[Circular] = list(circulars_result.scalars().all())

    # --- Single aggregation query on MapItem ---------------------------------
    agg_stmt = (
        select(
            MapItem.circular_id,
            func.count().label("total_maps"),
            func.count()
            .filter(MapItem.status == "satisfied")
            .label("maps_satisfied"),
            func.count()
            .filter(MapItem.status == "pending_review")
            .label("maps_pending_review"),
            func.count()
            .filter(MapItem.status == "overdue")
            .label("maps_overdue"),
            func.count()
            .filter(MapItem.status.in_(_IN_PROGRESS_STATUSES))
            .label("maps_in_progress"),
            func.min(MapItem.deadline)
            .filter(MapItem.status.notin_(("satisfied", "rejected")))
            .label("nearest_deadline"),
        )
        .group_by(MapItem.circular_id)
    )
    agg_result = await db.execute(agg_stmt)
    agg_by_circular: dict[UUID, dict] = {}
    for row in agg_result.all():
        agg_by_circular[row.circular_id] = {
            "total_maps": row.total_maps,
            "maps_satisfied": row.maps_satisfied,
            "maps_pending_review": row.maps_pending_review,
            "maps_overdue": row.maps_overdue,
            "maps_in_progress": row.maps_in_progress,
            "nearest_deadline": row.nearest_deadline,
        }

    # --- Merge ---------------------------------------------------------------
    now = datetime.now(timezone.utc)
    summaries: list[CircularSummary] = []
    for c in circulars:
        stats = agg_by_circular.get(c.id, {})
        nearest_dl = stats.get("nearest_deadline")
        days_to_nearest: int | None = None
        if nearest_dl is not None:
            # Ensure the deadline is timezone-aware for subtraction
            if nearest_dl.tzinfo is None:
                nearest_dl = nearest_dl.replace(tzinfo=timezone.utc)
            days_to_nearest = (nearest_dl - now).days

        summaries.append(
            CircularSummary(
                id=str(c.id),
                title=c.title,
                source_url=c.source_url,
                status=c.status,
                ingested_at=c.ingested_at,
                total_maps=stats.get("total_maps", 0),
                maps_satisfied=stats.get("maps_satisfied", 0),
                maps_pending_review=stats.get("maps_pending_review", 0),
                maps_overdue=stats.get("maps_overdue", 0),
                maps_in_progress=stats.get("maps_in_progress", 0),
                days_to_nearest_deadline=days_to_nearest,
            )
        )

    return summaries


# ---------------------------------------------------------------------------
# 2. GET /circulars/{circular_id}
# ---------------------------------------------------------------------------


@router.get("/circulars/{circular_id}", response_model=CircularDetailResponse)
async def get_circular_detail(
    circular_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CircularDetailResponse:
    """Return full circular detail with all MAPs, each enriched with the
    latest judgment and latest evidence submission.
    """
    # --- Load circular -------------------------------------------------------
    result = await db.execute(select(Circular).where(Circular.id == circular_id))
    circular: Circular | None = result.scalar_one_or_none()
    if circular is None:
        raise HTTPException(status_code=404, detail="Circular not found")

    # --- Load MAPs with eager-loaded relationships ---------------------------
    maps_result = await db.execute(
        select(MapItem)
        .where(MapItem.circular_id == circular_id)
        .options(
            selectinload(MapItem.children),
            selectinload(MapItem.judgments),
            selectinload(MapItem.evidence_submissions),
        )
        .order_by(MapItem.deadline.asc())
    )
    map_items: list[MapItem] = list(maps_result.scalars().all())

    maps_detail = [_build_map_detail(m, include_children=True) for m in map_items]

    return CircularDetailResponse(
        id=str(circular.id),
        title=circular.title,
        source_url=circular.source_url,
        raw_text=circular.raw_text,
        status=circular.status,
        ingested_at=circular.ingested_at,
        maps=maps_detail,
    )


# ---------------------------------------------------------------------------
# 3. GET /department/{department}
# ---------------------------------------------------------------------------


@router.get("/department/{department}", response_model=list[MapDetail])
async def list_maps_by_department(
    department: str,
    db: AsyncSession = Depends(get_db),
) -> list[MapDetail]:
    """Return all MAPs for a given department, ordered by overdue-first then
    earliest deadline.

    Raises 422 if the department name is not recognised.
    """
    if department not in DEPARTMENTS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid department '{department}'. "
                f"Must be one of: {', '.join(DEPARTMENTS)}"
            ),
        )

    overdue_first = case(
        (MapItem.status == "overdue", 1),
        else_=0,
    ).label("overdue_priority")

    maps_result = await db.execute(
        select(MapItem)
        .where(MapItem.department == department)
        .options(
            selectinload(MapItem.judgments),
            selectinload(MapItem.evidence_submissions),
        )
        .order_by(desc(overdue_first), MapItem.deadline.asc())
    )
    map_items: list[MapItem] = list(maps_result.scalars().all())

    return [_build_map_detail(m, include_children=False) for m in map_items]


# ---------------------------------------------------------------------------
# 4. GET /stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
) -> SystemStats:
    """Return top-level system statistics for circulars and MAPs."""
    # --- Circular counts -----------------------------------------------------
    circ_stmt = select(
        func.count().label("total_circulars"),
        func.count().filter(Circular.status == "compliant").label("compliant_circulars"),
        func.count().filter(Circular.status == "overdue").label("overdue_circulars"),
    ).select_from(Circular)
    circ_row = (await db.execute(circ_stmt)).one()

    # --- MAP counts ----------------------------------------------------------
    map_stmt = select(
        func.count().label("total_maps"),
        func.count().filter(MapItem.status == "pending_review").label("pending_review_maps"),
        func.count().filter(MapItem.status == "satisfied").label("satisfied_maps"),
        func.count().filter(MapItem.status == "overdue").label("overdue_maps"),
    ).select_from(MapItem)
    map_row = (await db.execute(map_stmt)).one()

    return SystemStats(
        total_circulars=circ_row.total_circulars,
        compliant_circulars=circ_row.compliant_circulars,
        overdue_circulars=circ_row.overdue_circulars,
        total_maps=map_row.total_maps,
        maps_pending_review=map_row.pending_review_maps,
        maps_satisfied=map_row.satisfied_maps,
        maps_overdue=map_row.overdue_maps,
    )
