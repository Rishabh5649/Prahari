"""Audit-log API – paginated listing and CSV export."""

import csv
import io
import json
import math
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogPage, AuditLogResponse

from app.api.deps import verify_api_key

router = APIRouter(
    prefix="/api/audit",
    tags=["Audit"],
    dependencies=[Depends(verify_api_key)]
)

# ──────────────────────────── helpers ────────────────────────────


def _apply_filters(
    stmt,
    *,
    event_type: str | None,
    entity_type: str | None,
    entity_id: str | None,
    actor: str | None,
):
    """Apply optional WHERE clauses to a SQLAlchemy statement."""
    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor == actor)
    return stmt


# ──────────────────────── GET /api/audit ─────────────────────────


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    actor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> AuditLogPage:
    """Return a paginated list of audit-log entries (newest first)."""

    filters = dict(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
    )

    # --- total count ---
    count_stmt = select(func.count()).select_from(AuditLog)
    count_stmt = _apply_filters(count_stmt, **filters)
    total: int = (await db.execute(count_stmt)).scalar_one()

    # --- data page ---
    data_stmt = select(AuditLog)
    data_stmt = _apply_filters(data_stmt, **filters)
    data_stmt = data_stmt.order_by(desc(AuditLog.created_at))
    data_stmt = data_stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(data_stmt)
    rows = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return AuditLogPage(
        items=[AuditLogResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ────────────────────── GET /api/audit/export ────────────────────

_CSV_COLUMNS = [
    "id",
    "event_type",
    "entity_type",
    "entity_id",
    "actor",
    "model_version",
    "input_hash",
    "output_hash",
    "created_at",
    "payload",
]


async def _csv_stream(
    db: AsyncSession,
    *,
    event_type: str | None,
    entity_type: str | None,
    entity_id: str | None,
    actor: str | None,
) -> AsyncGenerator[str, None]:
    """Yield CSV rows as string chunks."""

    # header
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    yield buf.getvalue()

    # data
    stmt = select(AuditLog)
    stmt = _apply_filters(
        stmt,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
    )
    stmt = stmt.order_by(desc(AuditLog.created_at))

    result = await db.execute(stmt)
    for row in result.scalars():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                row.id,
                row.event_type,
                row.entity_type,
                row.entity_id,
                row.actor,
                row.model_version,
                row.input_hash,
                row.output_hash,
                row.created_at.isoformat() if row.created_at else "",
                json.dumps(row.payload) if row.payload is not None else "",
            ]
        )
        yield buf.getvalue()


@router.get("/export")
async def export_audit_logs(
    event_type: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    actor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export the full (filtered) audit log as a downloadable CSV file."""

    return StreamingResponse(
        _csv_stream(
            db,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit_log_export.csv"
        },
    )
