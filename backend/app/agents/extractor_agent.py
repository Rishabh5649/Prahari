"""Extractor Agent — uses Claude to extract Mandatory Action Points from circulars."""

import json
import logging
from datetime import datetime, timedelta, timezone

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

class MapItemSchema(BaseModel):
    what: str = Field(description="Clear description of what must be done")
    deadline_text: str = Field(description="Raw deadline text from document, e.g. 'within 30 days', 'by 31 March 2025'")
    department: str = Field(description="One of: IT-Security, KYC/AML, Retail Banking, Treasury, Legal, Risk")
    evidence_type: str = Field(description="What would constitute acceptable proof, e.g. 'updated policy document', 'system log export'")
    confidence_score: float = Field(description="Float between 0 and 1, where 1 = certain and 0.5 = advisory")

class MapExtractionListSchema(BaseModel):
    maps: list[MapItemSchema]

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.models.map_item import MapItem
from app.utils.date_resolver import resolve_deadline
from app.utils.hashing import hash_content

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7

SYSTEM_PROMPT = (
    "You are a regulatory compliance analyst for an Indian bank. Your only task "
    "is to read an RBI/SEBI/DPDP circular and extract every Mandatory Action "
    "Point (MAP).\n\n"
    "A MAP is any instruction, requirement, or obligation that a bank must "
    "fulfil in response to this circular. It may include deadlines, required "
    "changes to policy, system updates, staff training, report submissions, or "
    "audit requirements.\n\n"
    "For each MAP, return a JSON object with EXACTLY these fields:\n"
    "{\n"
    '  "what": "<clear description of what must be done>",\n'
    '  "deadline_text": "<raw deadline text from document, e.g. '
    "'within 30 days', 'by 31 March 2025'>\",\n"
    '  "department": "<one of: IT-Security, KYC/AML, Retail Banking, '
    'Treasury, Legal, Risk>",\n'
    '  "evidence_type": "<what would constitute acceptable proof, e.g. '
    "'updated policy document', 'system log export', 'board resolution', "
    "'staff training attendance records'>\",\n"
    '  "confidence_score": <float between 0 and 1, where 1 = you are certain '
    "this is a mandatory requirement and 0.5 = it may be advisory>\n"
    "}\n\n"
    "Return ONLY a valid JSON array of these objects. No preamble, no "
    "explanation, no markdown. If you find no MAPs, return an empty array []."
)

RETRY_SUFFIX = "\n\nReturn ONLY raw JSON array, nothing else."

MODEL = "gemini-2.5-flash"


def _build_user_message(circular: Circular) -> str:
    """Construct the user message for the LLM."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"Here is the regulatory circular text:\n\n"
        f"{circular.raw_text}\n\n"
        f"Today's date is {today}. Extract all Mandatory Action Points."
    )


async def _call_gemini(user_message: str, retry: bool = False) -> list[dict]:
    """Call the Google Gemini API and parse the JSON response.

    Args:
        user_message: The user-role message containing the circular text.
        retry: If True, uses a stricter system prompt.

    Returns:
        Parsed list of MAP dictionaries.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    system = SYSTEM_PROMPT if not retry else SYSTEM_PROMPT + RETRY_SUFFIX

    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema=MapExtractionListSchema,
        ),
    )

    raw_text = response.text.strip()

    # Handle responses wrapped in markdown code fences
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        json_lines: list[str] = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                inside = True
                continue
            elif line.startswith("```") and inside:
                break
            if inside:
                json_lines.append(line)
        raw_text = "\n".join(json_lines)

    data = json.loads(raw_text)
    if isinstance(data, dict) and "maps" in data:
        return data["maps"]
    return data


async def extract_maps(
    circular: Circular, db: AsyncSession
) -> list[MapItem]:
    """Extract MAPs from a circular using Claude and persist them.

    Args:
        circular: The Circular ORM object with raw_text populated.
        db: Async database session.

    Returns:
        List of persisted MapItem ORM objects.
    """
    user_message = _build_user_message(circular)

    # First attempt
    try:
        maps_data = await _call_gemini(user_message)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("First LLM call failed (%s), retrying with stricter prompt…", exc)
        maps_data = await _call_gemini(user_message, retry=True)

    map_items: list[MapItem] = []
    pending_count = 0
    assigned_count = 0

    input_hash = hash_content(circular.raw_text)

    # Ensure base_date is timezone-aware
    base_date = circular.ingested_at
    if base_date.tzinfo is None:
        base_date = base_date.replace(tzinfo=timezone.utc)

    for entry in maps_data:
        # Resolve deadline
        try:
            deadline = resolve_deadline(entry["deadline_text"], base_date=base_date)
        except (ValueError, KeyError):
            logger.warning(
                "Could not resolve deadline '%s', defaulting to 90 days from ingestion",
                entry.get("deadline_text", "<missing>"),
            )
            deadline = base_date + timedelta(days=90)

        confidence = float(entry.get("confidence_score", 0.5))
        if confidence < CONFIDENCE_THRESHOLD:
            status = "pending_review"
            pending_count += 1
        else:
            status = "assigned"
            assigned_count += 1

        map_item = MapItem(
            circular_id=circular.id,
            what=entry["what"],
            deadline=deadline,
            department=entry["department"],
            evidence_type=entry["evidence_type"],
            confidence_score=confidence,
            status=status,
        )
        db.add(map_item)
        await db.flush()  # populate map_item.id

        # Audit log for each extracted MAP
        map_payload = {
            "what": entry["what"],
            "deadline_text": entry.get("deadline_text", ""),
            "department": entry["department"],
            "evidence_type": entry["evidence_type"],
            "confidence_score": confidence,
            "resolved_deadline": deadline.isoformat(),
            "status": status,
        }
        audit = AuditLog(
            event_type="map_extracted",
            entity_type="map_item",
            entity_id=str(map_item.id),
            payload=map_payload,
            input_hash=input_hash,
            output_hash=hash_content(json.dumps(map_payload, sort_keys=True)),
            model_version=MODEL,
            actor="system",
        )
        db.add(audit)

        map_items.append(map_item)

    # Update circular status
    circular.status = "in_progress"
    await db.flush()

    # Final summary audit log
    completion_audit = AuditLog(
        event_type="extraction_complete",
        entity_type="circular",
        entity_id=str(circular.id),
        payload={
            "total_maps": len(map_items),
            "pending_review": pending_count,
            "auto_assigned": assigned_count,
        },
        actor="system",
    )
    db.add(completion_audit)
    await db.flush()

    return map_items
