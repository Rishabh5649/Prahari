"""Seed script — creates a sample circular with parseable MAPs for demo purposes.

Usage:
    cd backend
    python seed.py
"""

import asyncio
import hashlib
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed")

# Placeholder raw text that mimics a real RBI circular with 3 clear MAPs
SAMPLE_RAW_TEXT = """
RESERVE BANK OF INDIA
DEPARTMENT OF INFORMATION TECHNOLOGY
CIRCULAR NO. RBI/2024-25/123

DATE: January 15, 2025
TO: All Scheduled Commercial Banks

SUBJECT: Master Direction on Information Technology Framework for Banks — 2024 Update

In exercise of the powers conferred under Section 35A of the Banking Regulation Act, 1949,
the Reserve Bank of India hereby directs all scheduled commercial banks to comply with the
following requirements:

1. MANDATORY ENCRYPTION FOR CUSTOMER DATA AT REST

All banks shall ensure that all customer Personally Identifiable Information (PII) stored
in their core banking systems, data warehouses, and backup media is encrypted using
AES-256 or equivalent encryption standards. Banks must complete migration of all existing
unencrypted data stores by June 30, 2025. Evidence of compliance shall include an
independent audit report from a CERT-In empanelled auditor confirming full encryption
coverage across all identified data stores.

Department: IT-Security
Expected evidence: Independent audit report from CERT-In empanelled auditor

2. ENHANCED KYC RE-VERIFICATION FOR HIGH-RISK ACCOUNTS

All banks shall implement a periodic KYC re-verification process for accounts classified
as high-risk under the bank's Customer Due Diligence (CDD) framework. Re-verification
must be completed at least once every six months and must include updated proof of
identity, proof of address, and source of funds declaration. Banks shall submit a compliance
report to RBI by March 31, 2025. Evidence shall include a sample of 50 re-verified
account records and the updated CDD policy document.

Department: KYC/AML
Expected evidence: Sample re-verified records and updated CDD policy document

3. BOARD-APPROVED CYBER INCIDENT RESPONSE PLAN

Each bank shall adopt a Board-approved Cyber Incident Response Plan (CIRP) that
includes defined escalation procedures, communication protocols with CERT-In, and
quarterly mock drill schedules. The CIRP must be reviewed and updated annually. Banks
must submit proof of Board approval and the most recent mock drill report to RBI by
April 30, 2025.

Department: IT-Security
Expected evidence: Board resolution approving CIRP and latest mock drill report

Yours faithfully,
(Authorized Signatory)
Reserve Bank of India
"""


async def main():
    """Run the seed flow."""
    # Late imports so environment is ready
    from app.core.database import async_session_factory
    from app.models.circular import Circular
    from app.models.audit_log import AuditLog
    from app.agents.extractor_agent import extract_maps
    from app.services.routing_service import route_all_maps
    from app.utils.hashing import hash_content
    from app.utils.pdf_parser import section_text

    logger.info("Starting seed...")

    cleaned = section_text(SAMPLE_RAW_TEXT)
    content_hash = hash_content(cleaned)

    async with async_session_factory() as session:
        # Check for duplicate
        from sqlalchemy import select
        result = await session.execute(
            select(Circular).where(Circular.source_hash == content_hash)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.warning("Seed circular already exists (id=%s). Skipping.", existing.id)
            return

        # Create circular
        circular = Circular(
            source_url=None,
            source_hash=content_hash,
            raw_text=cleaned,
            status="processing",
            title="RBI Master Direction on IT Framework 2024",
        )
        session.add(circular)
        await session.flush()

        # Audit log
        audit = AuditLog(
            event_type="circular_ingested",
            entity_type="circular",
            entity_id=str(circular.id),
            payload={"source": "seed_script", "char_count": len(cleaned)},
            input_hash=content_hash,
            actor="seed_script",
        )
        session.add(audit)
        await session.flush()

        logger.info("Created circular: id=%s", circular.id)

        # Extract MAPs
        try:
            map_items = await extract_maps(circular, session)
            logger.info("Extracted %d MAPs", len(map_items))
        except Exception as exc:
            logger.error("MAP extraction failed: %s", exc)
            logger.info(
                "Skipping extraction (requires ANTHROPIC_API_KEY). "
                "Circular was still created — you can extract MAPs via the /ingest API."
            )
            await session.commit()
            return

        # Route MAPs
        try:
            await route_all_maps(circular, map_items, session)
            logger.info("Routed all MAPs")
        except Exception as exc:
            logger.error("Routing failed: %s", exc)

        await session.commit()

    logger.info("Seed complete!")
    logger.info(
        "View at: http://localhost:5173/circular/<id> (start frontend first)"
    )


if __name__ == "__main__":
    asyncio.run(main())
