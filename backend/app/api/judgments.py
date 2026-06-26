"""Judgments API router.

Provides endpoints for triggering AI-based evidence judgment,
applying human overrides, and retrieving judgment history.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.judge_agent import judge_evidence, override_judgment
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment
from app.models.map_item import MapItem
from app.schemas.judgment import JudgeRequest, JudgmentResponse, OverrideRequest

router = APIRouter(prefix="/api/judgments", tags=["Judgments"])

VALID_VERDICTS = {"satisfied", "partial", "insufficient"}



@router.post("/{map_id}/judge", response_model=JudgmentResponse)
async def judge_map_evidence(
    map_id: UUID,
    request: JudgeRequest,
    db: AsyncSession = Depends(get_db),
) -> JudgmentResponse:
    """Trigger the judge agent to evaluate submitted evidence for a map item.

    The map item must be in 'evidence_submitted' status and the evidence
    must belong to the specified map item.

    Args:
        map_id: The UUID of the map item to judge.
        request: Body containing the evidence_id to evaluate.
        db: Async database session.

    Returns:
        The resulting judgment record.

    Raises:
        HTTPException 404: If the map item or evidence submission is not found.
        HTTPException 400: If the map item is not ready for judging or the
            evidence does not belong to the specified map item.
    """
    # Load and validate the map item
    result = await db.execute(select(MapItem).where(MapItem.id == map_id))
    map_item = result.scalar_one_or_none()
    if map_item is None:
        raise HTTPException(status_code=404, detail="Map item not found")

    if map_item.status != "evidence_submitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot judge: map item does not have submitted evidence",
        )

    # Load and validate the evidence submission
    evidence_id = UUID(request.evidence_id)
    result = await db.execute(
        select(EvidenceSubmission).where(EvidenceSubmission.id == evidence_id)
    )
    evidence = result.scalar_one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence submission not found")

    if evidence.map_id != map_id:
        raise HTTPException(
            status_code=400,
            detail="Evidence does not belong to the specified map item",
        )

    # Transition status and invoke the judge agent
    map_item.status = "judging"
    await db.flush()

    judgment = await judge_evidence(map_item, evidence, db)
    return judgment


@router.post("/{judgment_id}/override", response_model=JudgmentResponse)
async def override_existing_judgment(
    judgment_id: UUID,
    body: OverrideRequest,
    db: AsyncSession = Depends(get_db),
) -> JudgmentResponse:
    """Apply a human override to an existing judgment.

    Args:
        judgment_id: The UUID of the judgment to override.
        body: Override details including new verdict, overrider identity,
            and reason for the override.
        db: Async database session.

    Returns:
        The updated judgment record.

    Raises:
        HTTPException 400: If the new verdict is not a valid option.
        HTTPException 404: If the judgment is not found.
    """
    if body.new_verdict not in VALID_VERDICTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verdict '{body.new_verdict}'. Must be one of: {', '.join(sorted(VALID_VERDICTS))}",
        )

    # 1. Fetch current latest judgment
    result = await db.execute(select(Judgment).where(Judgment.id == judgment_id))
    current_judgment = result.scalar_one_or_none()
    if current_judgment is None:
        raise HTTPException(status_code=404, detail="Judgment not found")

    # Fetch corresponding MapItem
    map_result = await db.execute(
        select(MapItem).where(MapItem.id == current_judgment.map_id)
    )
    map_item = map_result.scalar_one_or_none()
    if map_item is None:
        raise HTTPException(status_code=404, detail="Associated MAP item not found")

    # 3. Create a new Judgment object
    new_judgment = Judgment(
        map_id=current_judgment.map_id,
        evidence_id=current_judgment.evidence_id,  # carry forward
        verdict=body.new_verdict,
        reasoning=f"Human override: {body.override_reason}",
        human_override=True,
        override_by=body.override_by,
        override_reason=body.override_reason,
    )
    db.add(new_judgment)
    await db.flush()

    # 4. Update map_item.status to match the new verdict
    map_item.status = body.new_verdict
    await db.flush()

    # 5. Write audit_log
    audit = AuditLog(
        event_type="human_override",
        entity_type="judgment",
        entity_id=str(new_judgment.id),
        payload={
            "previous_verdict": current_judgment.verdict,
            "new_verdict": body.new_verdict,
            "previous_judgment_id": str(current_judgment.id),
            "new_judgment_id": str(new_judgment.id),
            "by": body.override_by,
            "reason": body.override_reason,
        },
        actor=body.override_by,
    )
    db.add(audit)
    await db.flush()

    # 6. Return the new judgment object
    return new_judgment


@router.get("/{map_id}", response_model=list[JudgmentResponse])
async def list_judgments_for_map(
    map_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[JudgmentResponse]:
    """Retrieve all judgments for a given map item, newest first.

    Args:
        map_id: The UUID of the map item whose judgments to retrieve.
        db: Async database session.

    Returns:
        A list of judgment records ordered by judged_at descending.
    """
    result = await db.execute(
        select(Judgment)
        .where(Judgment.map_id == map_id)
        .order_by(Judgment.judged_at.desc())
    )
    judgments = result.scalars().all()
    return judgments
