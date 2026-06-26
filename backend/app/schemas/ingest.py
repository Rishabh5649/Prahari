"""Pydantic schemas for the Ingest API."""

from pydantic import BaseModel


class IngestURLRequest(BaseModel):
    """Request body for URL-based circular ingestion."""

    url: str


class IngestResponse(BaseModel):
    """Response after ingesting a circular and extracting MAPs."""

    circular_id: str
    status: str
    maps_extracted: int
    pending_review: int
