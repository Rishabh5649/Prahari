from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    input_hash: str | None = None
    output_hash: str | None = None
    model_version: str | None = None
    actor: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
