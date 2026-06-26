"""Ingest API router — URL and file upload endpoints for regulatory circulars."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.extractor_agent import extract_maps
from app.core.database import get_db
from app.schemas.ingest import IngestResponse, IngestURLRequest
from app.services.ingest_service import ingest_from_upload, ingest_from_url
from app.services.routing_service import route_all_maps

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/url", response_model=IngestResponse)
async def ingest_url_endpoint(
    body: IngestURLRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a regulatory circular from a public URL and extract MAPs."""
    try:
        circular = await ingest_from_url(body.url, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {exc}")

    map_items = await extract_maps(circular, db)
    await route_all_maps(circular, map_items, db)
    pending = sum(1 for m in map_items if m.status == "pending_review")

    return IngestResponse(
        circular_id=str(circular.id),
        status=circular.status,
        maps_extracted=len(map_items),
        pending_review=pending,
    )


@router.post("/upload", response_model=IngestResponse)
async def ingest_upload_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a regulatory circular from an uploaded PDF file and extract MAPs."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

    try:
        circular = await ingest_from_upload(file.filename, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse PDF file. Ensure it is a valid PDF document. Details: {exc}"
        )

    map_items = await extract_maps(circular, db)
    await route_all_maps(circular, map_items, db)
    pending = sum(1 for m in map_items if m.status == "pending_review")

    return IngestResponse(
        circular_id=str(circular.id),
        status=circular.status,
        maps_extracted=len(map_items),
        pending_review=pending,
    )
