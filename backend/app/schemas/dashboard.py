"""Pydantic schemas for the Dashboard API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


# --- Circular summary (for GET /api/dashboard/circulars) ---

class CircularSummary(BaseModel):
    """Circular with aggregated MAP stats."""
    id: str
    title: str | None = None
    source_url: str | None = None
    status: str
    ingested_at: datetime
    total_maps: int
    maps_satisfied: int
    maps_pending_review: int
    maps_overdue: int
    maps_in_progress: int
    days_to_nearest_deadline: int | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


# --- Latest judgment brief (embedded in MAP detail) ---

class LatestJudgmentBrief(BaseModel):
    verdict: str
    reasoning: str
    judged_at: datetime
    human_override: bool


# --- Latest evidence brief (embedded in MAP detail) ---

class LatestEvidenceBrief(BaseModel):
    file_name: str
    submitted_by: str
    submitted_at: datetime


# --- Child MAP brief (for split MAPs) ---

class ChildMapBrief(BaseModel):
    id: str
    department: str
    status: str

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v


# --- MAP detail (used in circular detail and department views) ---

class MapDetail(BaseModel):
    """Full MAP detail with latest judgment and evidence."""
    id: str
    what: str
    department: str
    deadline: datetime
    status: str
    confidence_score: float
    parent_map_id: str | None = None
    children: list[ChildMapBrief] = []
    latest_judgment: LatestJudgmentBrief | None = None
    latest_evidence: LatestEvidenceBrief | None = None

    @field_validator("id", "parent_map_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if v is None:
            return v
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


# --- Circular detail response (for GET /api/dashboard/circulars/{id}) ---

class CircularDetailResponse(BaseModel):
    """Full circular detail with all MAPs."""
    id: str
    title: str | None = None
    source_url: str | None = None
    status: str
    ingested_at: datetime
    raw_text: str
    maps: list[MapDetail] = []

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


# --- System stats (for GET /api/dashboard/stats) ---

class SystemStats(BaseModel):
    """Top-level system stats for header widgets."""
    total_circulars: int
    compliant_circulars: int
    overdue_circulars: int
    failed_circulars: int
    total_maps: int
    maps_pending_review: int
    maps_satisfied: int
    maps_overdue: int
