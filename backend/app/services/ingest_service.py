"""Ingestion service — downloads, parses, deduplicates, and stores circulars."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.utils.hashing import hash_content
from app.utils.pdf_parser import parse_pdf_bytes, parse_url, section_text


async def _persist_circular(
    raw_text: str,
    source_url: str | None,
    db: AsyncSession,
) -> Circular:
    """Hash, deduplicate, persist, and audit-log a circular."""
    cleaned = section_text(raw_text)
    content_hash = hash_content(cleaned)

    # Duplicate check
    result = await db.execute(
        select(Circular).where(Circular.source_hash == content_hash)
    )
    if result.scalar_one_or_none() is not None:
        raise ValueError("Duplicate circular")

    circular = Circular(
        source_url=source_url,
        source_hash=content_hash,
        raw_text=cleaned,
        status="processing",
    )
    db.add(circular)
    await db.flush()  # populate circular.id

    # Audit log
    audit = AuditLog(
        event_type="circular_ingested",
        entity_type="circular",
        entity_id=str(circular.id),
        payload={"url": source_url, "char_count": len(cleaned)},
        input_hash=content_hash,
        actor="system",
    )
    db.add(audit)
    await db.flush()

    return circular


async def ingest_from_url(url: str, db: AsyncSession) -> Circular:
    """Ingest a regulatory circular by downloading from a URL.

    Args:
        url: Public URL of the circular (PDF or HTML page).
        db: Async database session.

    Returns:
        The persisted Circular ORM object.

    Raises:
        ValueError: If a circular with the same content hash already exists.
    """
    raw_text = parse_url(url)
    return await _persist_circular(raw_text, source_url=url, db=db)


async def ingest_from_upload(
    filename: str, data: bytes, db: AsyncSession
) -> Circular:
    """Ingest a regulatory circular from an uploaded PDF file.

    Args:
        filename: Original filename of the uploaded PDF.
        data: Raw PDF bytes.
        db: Async database session.

    Returns:
        The persisted Circular ORM object.

    Raises:
        ValueError: If a circular with the same content hash already exists.
    """
    raw_text = parse_pdf_bytes(data)
    return await _persist_circular(raw_text, source_url=None, db=db)
