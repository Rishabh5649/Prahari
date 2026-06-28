from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.models.circular import Circular
from app.schemas.ingest import IngestResponse, IngestURLRequest
from app.services.ingest_service import ingest_from_upload, ingest_from_url, run_ingestion_pipeline

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/url", status_code=202)
async def ingest_url_endpoint(
    body: IngestURLRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a regulatory circular from a public URL (async)."""
    try:
        circular = await ingest_from_url(body.url, db)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {exc}")

    background_tasks.add_task(run_ingestion_pipeline, str(circular.id), async_session_factory)
    
    return {
        "job_id": str(circular.id),
        "status": "queued"
    }


@router.post("/upload", status_code=202)
async def ingest_upload_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a regulatory circular from an uploaded PDF file (async)."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

    try:
        circular = await ingest_from_upload(file.filename, data, db)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse PDF file. Ensure it is a valid PDF document. Details: {exc}"
        )

    background_tasks.add_task(run_ingestion_pipeline, str(circular.id), async_session_factory)

    return {
        "job_id": str(circular.id),
        "status": "queued"
    }


@router.get("/status/{job_id}")
async def get_ingest_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check the status of a background ingestion job."""
    result = await db.execute(select(Circular).where(Circular.id == job_id))
    circular = result.scalar_one_or_none()
    if not circular:
        raise HTTPException(status_code=404, detail="Job/Circular not found")
    
    return {
        "job_id": str(circular.id),
        "status": circular.status,
        "title": circular.title
    }
