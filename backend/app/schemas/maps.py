"""Pydantic schemas for the MAPs API."""

from datetime import datetime

from pydantic import BaseModel


class MapItemResponse(BaseModel):
    """Response schema for a MAP item."""

    id: str
    circular_id: str
    parent_map_id: str | None = None
    what: str
    deadline: datetime
    department: str
    evidence_type: str
    confidence_score: float
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class EvidenceBrief(BaseModel):
    """Brief evidence submission for embedding in MAP detail."""

    id: str
    file_name: str
    submitted_by: str
    submitted_at: datetime

    class Config:
        from_attributes = True


class JudgmentBrief(BaseModel):
    """Brief judgment for embedding in MAP detail."""

    id: str
    verdict: str
    reasoning: str
    human_override: bool
    judged_at: datetime

    class Config:
        from_attributes = True


class MapDetailResponse(BaseModel):
    """Detailed MAP response with evidence submissions and judgments."""

    id: str
    circular_id: str
    parent_map_id: str | None = None
    what: str
    deadline: datetime
    department: str
    evidence_type: str
    confidence_score: float
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    evidence_submissions: list[EvidenceBrief] = []
    judgments: list[JudgmentBrief] = []
    children: list[MapItemResponse] = []

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    """Body for human-approving a pending_review MAP."""

    approved_by: str


class RejectRequest(BaseModel):
    """Body for human-rejecting a MAP."""

    rejected_by: str
    reason: str
