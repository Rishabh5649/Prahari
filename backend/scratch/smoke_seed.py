import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.circular import Circular
from app.models.map_item import MapItem
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment

async def main():
    async with async_session_factory() as session:
        # Get the seeded circular
        result = await session.execute(select(Circular).order_by(Circular.ingested_at.desc()))
        circular = result.scalars().first()
        if not circular:
            print("No circular found. Please run seed.py first.")
            return

        circular_id = circular.id
        print(f"Using circular ID: {circular_id}")

        # Delete related judgments, evidence submissions, and maps to clean up cleanly
        stmt = select(MapItem).where(MapItem.circular_id == circular_id)
        res = await session.execute(stmt)
        map_items = res.scalars().all()
        map_ids = [m.id for m in map_items]

        if map_ids:
            # Delete judgments
            judgements_stmt = select(Judgment).where(Judgment.map_id.in_(map_ids))
            judgements_res = await session.execute(judgements_stmt)
            for j in judgements_res.scalars().all():
                await session.delete(j)

            # Delete evidence submissions
            evidence_stmt = select(EvidenceSubmission).where(EvidenceSubmission.map_id.in_(map_ids))
            evidence_res = await session.execute(evidence_stmt)
            for e in evidence_res.scalars().all():
                await session.delete(e)

            await session.flush()

            # Delete map items
            for m in map_items:
                await session.delete(m)
            await session.flush()

        # Add 2 sample MAPs
        map1 = MapItem(
            circular_id=circular_id,
            what="Implement AES-256 encryption for all customer data at rest.",
            deadline=datetime.now(timezone.utc) + timedelta(days=90),
            department="IT-Security",
            evidence_type="Independent audit report from CERT-In empanelled auditor",
            confidence_score=0.95,
            status="assigned"
        )
        map2 = MapItem(
            circular_id=circular_id,
            what="Conduct periodic KYC re-verification for high-risk accounts.",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="KYC/AML",
            evidence_type="Sample re-verified records and updated CDD policy document",
            confidence_score=0.65,
            status="pending_review"
        )
        session.add(map1)
        session.add(map2)
        await session.commit()
        print("Successfully seeded 2 MapItems for smoke testing.")

if __name__ == "__main__":
    asyncio.run(main())
