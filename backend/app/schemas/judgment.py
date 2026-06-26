"""Pydantic schemas for the Judgment API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class JudgmentResponse(BaseModel):
    """Serialised judgment returned by the API."""

    id: str
    map_id: str
    evidence_id: str
    verdict: str
    reasoning: str
    human_override: bool
    override_by: str | None = None
    override_reason: str | None = None
    judged_at: datetime

    @field_validator("id", "map_id", "evidence_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class JudgeRequest(BaseModel):
    """Trigger judgment for a MAP's evidence."""

    evidence_id: str


class OverrideRequest(BaseModel):
    """Human override of an LLM judgment."""

    new_verdict: str  # Must be: satisfied, partial, insufficient
    override_by: str
    override_reason: str
