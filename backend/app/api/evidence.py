"""Evidence API router — submit evidence and download files."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.minio_client import minio_client
from app.models.evidence import EvidenceSubmission
from app.schemas.evidence import EvidenceSubmitResponse
from app.services.evidence_service import submit_evidence

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])

MAX_EVIDENCE_SIZE = 20 * 1024 * 1024  # 20 MB


def stream_minio_object(bucket: str, key: str):
    """Generator to read and stream MinIO object in chunks, closing connections cleanly."""
    response = minio_client.get_object(bucket, key)
    try:
        while True:
            chunk = response.read(64 * 1024)  # 64 KB chunks
            if not chunk:
                break
            yield chunk
    finally:
        response.close()
        response.release_conn()


@router.post("/submit", response_model=EvidenceSubmitResponse)
async def submit_evidence_endpoint(
    map_id: UUID = Form(..., description="UUID of the MAP item"),
    submitted_by: str = Form(..., description="Officer name or email"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload evidence for a MAP item."""
    if file.size and file.size > MAX_EVIDENCE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

    file_data = await file.read()
    if len(file_data) > MAX_EVIDENCE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

    file_name = file.filename or "unnamed"

    evidence = await submit_evidence(
        map_id=map_id,
        file_name=file_name,
        file_data=file_data,
        submitted_by=submitted_by,
        db=db,
    )

    return EvidenceSubmitResponse(
        evidence_id=str(evidence.id),
        map_id=str(evidence.map_id),
        minio_key=evidence.minio_object_key,
        status="evidence_submitted",
    )


@router.get("/download/{evidence_id}")
async def download_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download an evidence file from MinIO."""
    result = await db.execute(
        select(EvidenceSubmission).where(EvidenceSubmission.id == evidence_id)
    )
    evidence = result.scalar_one_or_none()

    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence submission not found")

    # Verify key exists in MinIO first, offloading to thread pool
    try:
        await run_in_threadpool(
            minio_client.stat_object,
            settings.MINIO_BUCKET,
            evidence.minio_object_key,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"File not found in storage: {exc}"
        )

    # Stream chunks dynamically using standard generator
    return StreamingResponse(
        stream_minio_object(settings.MINIO_BUCKET, evidence.minio_object_key),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.file_name}"'
        },
    )
