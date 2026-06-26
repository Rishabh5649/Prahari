import asyncio
import json
import requests
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.map_item import MapItem
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment

BASE_URL = "http://localhost:8000"

async def setup_data():
    async with async_session_factory() as session:
        # Get an assigned map item
        result = await session.execute(select(MapItem).where(MapItem.status == 'assigned'))
        map_item = result.scalars().first()
        if not map_item:
            print("No assigned map item found. Run seed and smoke_seed first.")
            return None, None

        # Insert a dummy evidence submission
        evidence = EvidenceSubmission(
            map_id=map_item.id,
            file_name="fake_evidence.txt",
            minio_object_key="evidence/fake.txt",
            submitted_by="test@bank.com"
        )
        session.add(evidence)
        await session.flush()

        # Insert an initial AI judgment
        judgment = Judgment(
            map_id=map_item.id,
            evidence_id=evidence.id,
            verdict="insufficient",
            reasoning="AI reasoning: Missing encryption records.",
            human_override=False
        )
        session.add(judgment)
        await session.commit()
        
        print(f"Set up dummy judgment: ID={judgment.id}, MAP_ID={map_item.id}, Verdict={judgment.verdict}")
        return str(judgment.id), str(map_item.id)

def trigger_override(judgment_id):
    url = f"{BASE_URL}/api/judgments/{judgment_id}/override"
    payload = {
        "new_verdict": "satisfied",
        "override_by": "officer@bank.com",
        "override_reason": "Audited evidence manually, looks correct."
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers)
    print(f"POST Override Status Code: {r.status_code}")
    print("POST Override Response:")
    print(json.dumps(r.json(), indent=2))

async def verify_db(map_id):
    print("\n--- Current judgments in Database ---")
    async with async_session_factory() as session:
        result = await session.execute(
            select(Judgment)
            .where(Judgment.map_id == map_id)
            .order_by(Judgment.judged_at.asc())
        )
        judgments = result.scalars().all()
        for idx, j in enumerate(judgments):
            print(f"Row {idx+1}:")
            print(f"  ID: {j.id}")
            print(f"  Verdict: {j.verdict}")
            print(f"  Reasoning: {j.reasoning}")
            print(f"  Human Override: {j.human_override}")
            print(f"  Override By: {j.override_by}")
            print(f"  Override Reason: {j.override_reason}")
            print(f"  Judged At: {j.judged_at}")
            print()

async def run_flow():
    judgment_id, map_id = await setup_data()
    if not judgment_id:
        return
    trigger_override(judgment_id)
    await verify_db(map_id)

if __name__ == "__main__":
    asyncio.run(run_flow())
