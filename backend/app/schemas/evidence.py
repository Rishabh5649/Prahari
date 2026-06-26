"""Pydantic schemas for the Evidence API."""

from pydantic import BaseModel


class EvidenceSubmitResponse(BaseModel):
    """Response after submitting evidence for a MAP."""

    evidence_id: str
    map_id: str
    minio_key: str
    status: str
