"""Ingestion service — downloads, parses, deduplicates, and stores circulars."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.utils.hashing import hash_content
from app.utils.pdf_parser import parse_pdf_bytes, parse_url, section_text

def extract_title(text: str) -> str:
    """Try to extract a title from raw circular text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Untitled Circular"

    for line in lines:
        if len(line) > 120:
            continue
        
        # Heading markers
        is_heading = (
            line.isupper() or 
            line.startswith(("Circular", "Notification", "RBI", "SEBI", "Master Direction"))
        )
        if is_heading:
            return line[:120]

    # Fallback to first line
    return lines[0][:120]


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
        title=extract_title(cleaned),
        status="queued",
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
    import asyncio
    raw_text = await asyncio.to_thread(parse_url, url)
    return await _persist_circular(raw_text, source_url=url, db=db)


async def ingest_from_upload(
    filename: str, data: bytes, db: AsyncSession
) -> Circular:
    """Ingest a regulatory circular from an uploaded PDF file."""
    import asyncio
    raw_text = await asyncio.to_thread(parse_pdf_bytes, data)
    return await _persist_circular(raw_text, source_url=None, db=db)

async def run_ingestion_pipeline(circular_id: str, db_factory):
    """Full 5-stage pipeline run in background."""
    from app.agents.extractor_agent import extract_maps
    from app.services.routing_service import route_all_maps
    
    async with db_factory() as db:
        result = await db.execute(select(Circular).where(Circular.id == circular_id))
        circular = result.scalar_one_or_none()
        if not circular:
            return

        try:
            circular.status = "processing"
            await db.flush()
            
            # Stage 2: Extract MAPs
            maps = await extract_maps(circular, db)
            
            # Stage 3: Route MAPs
            await route_all_maps(circular, maps, db)
            
            # Stage 4 & 5 (Judgement) are triggered when evidence is submitted
            
            await db.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Ingestion pipeline failed for %s", circular_id)
            try:
                await db.rollback()
            except Exception:
                pass

            # Use a fresh connection to write the failure state safely
            async with db_factory() as fail_db:
                result = await fail_db.execute(select(Circular).where(Circular.id == circular_id))
                fail_circ = result.scalar_one_or_none()
                if fail_circ:
                    fail_circ.status = "failed"
                    audit = AuditLog(
                        event_type="ingestion_failed",
                        entity_type="circular",
                        entity_id=str(fail_circ.id),
                        payload={"error": str(exc)},
                        actor="system",
                    )
                    fail_db.add(audit)
                    await fail_db.commit()
            raise
