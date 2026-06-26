"""Judge Agent — uses Claude to evaluate evidence against MAP requirements.

This agent is completely independent of the extractor agent. It has no knowledge
of the extraction step. Its sole purpose is to read a MAP requirement alongside
submitted evidence and return a compliance verdict.
"""

import json
import logging
from io import BytesIO

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

class JudgeVerdictSchema(BaseModel):
    verdict: str = Field(description="One of: satisfied, partial, insufficient")
    reasoning: str = Field(description="A paragraph that cites specifically what in the evidence meets or fails the requirement")
    gaps: list[str] = Field(default=[], description="List each gap or missing item if any")

from app.core.config import settings
from app.core.minio_client import minio_client
from app.models.audit_log import AuditLog
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment
from app.models.map_item import MapItem
from app.utils.hashing import hash_content

logger = logging.getLogger(__name__)

# MODEL removed here, now using settings.MODEL

SYSTEM_PROMPT = (
    "You are an independent compliance auditor for an Indian bank. You have NO "
    "prior knowledge of how requirements were extracted. Your only task is to "
    "evaluate whether submitted evidence satisfies a specific regulatory "
    "requirement.\n\n"
    "You will receive:\n"
    "1. The original regulatory requirement (what must be done, what evidence "
    "is expected).\n"
    "2. The submitted evidence (document text or description).\n\n"
    "Return ONLY a JSON object with EXACTLY these fields:\n"
    "{\n"
    '  "verdict": "<one of: satisfied, partial, insufficient>",\n'
    '  "reasoning": "<a paragraph that cites specifically what in the evidence '
    'meets or fails the requirement>",\n'
    '  "gaps": ["<list each gap or missing item if any>"]\n'
    "}\n\n"
    "Rules:\n"
    "- 'satisfied' → evidence fully demonstrates compliance.\n"
    "- 'partial' → evidence shows some compliance but has specific gaps.\n"
    "- 'insufficient' → evidence does not meaningfully address the requirement.\n"
    "- Be rigorous. A policy document that merely states intent without "
    "implementation details is 'partial' at best.\n"
    "- If the evidence is unreadable or empty, return 'insufficient' with "
    "reasoning explaining why."
)

RETRY_SUFFIX = "\n\nReturn ONLY raw JSON object, nothing else."


async def _extract_evidence_text(evidence: EvidenceSubmission) -> str:
    """Download and extract readable text from an evidence file stored in MinIO.

    Supports PDF (via pdf_parser), plain text files (.txt, .md, .csv),
    and returns a placeholder description for binary formats.

    Args:
        evidence: The EvidenceSubmission ORM object with minio_object_key.

    Returns:
        Extracted text content or a descriptive fallback string.
    """
    try:
        response = minio_client.get_object(
            settings.MINIO_BUCKET, evidence.minio_object_key
        )
        data = response.read()
        response.close()
        response.release_conn()

        file_name_lower = evidence.file_name.lower()

        if file_name_lower.endswith(".pdf"):
            from app.utils.pdf_parser import parse_pdf_bytes

            return parse_pdf_bytes(data)
        elif file_name_lower.endswith((".txt", ".md", ".csv")):
            return data.decode("utf-8")
        else:
            return f"[Binary file: {evidence.file_name}, {len(data)} bytes]"
    except Exception as e:
        logger.error("Failed to extract evidence text for %s: %s", evidence.id, e)
        return f"[Error reading evidence file: {str(e)}]"


async def _call_anthropic(user_message: str, retry: bool = False) -> dict:
    """Call the Anthropic API and parse the JSON response.

    Args:
        user_message: The user-role message containing requirement and evidence.
        retry: If True, appends a stricter suffix to the system prompt.

    Returns:
        Parsed verdict dictionary with verdict, reasoning, and gaps.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    system = SYSTEM_PROMPT if not retry else SYSTEM_PROMPT + RETRY_SUFFIX

    response = await client.messages.create(
        model=settings.MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()

    # Handle responses wrapped in markdown code fences
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        json_lines: list[str] = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                if "json" in line.lower():
                    inside = True
                    continue
                inside = True
                continue
            elif line.startswith("```") and inside:
                break
            if inside:
                json_lines.append(line)
        raw_text = "\n".join(json_lines)

    return json.loads(raw_text)


MAX_EVIDENCE_CHARS = 6000

async def judge_evidence(
    map_item: MapItem,
    evidence: EvidenceSubmission,
    db: AsyncSession,
) -> Judgment:
    """Evaluate submitted evidence against a MAP requirement using Claude.

    Downloads the evidence file, sends it with the MAP requirement to the LLM,
    parses the verdict, persists a Judgment record, updates the MAP status,
    and creates an audit log entry.

    Args:
        map_item: The MapItem ORM object describing the regulatory requirement.
        evidence: The EvidenceSubmission ORM object to evaluate.
        db: Async database session.

    Returns:
        The persisted Judgment ORM object.
    """
    evidence_text = await _extract_evidence_text(evidence)

    # Log warning if truncation occurrs
    original_len = len(evidence_text)
    if original_len > MAX_EVIDENCE_CHARS:
        logger.warning(
            "Evidence for MAP %s truncated from %d to %d chars",
            map_item.id,
            original_len,
            MAX_EVIDENCE_CHARS
        )

    # Cap at MAX_EVIDENCE_CHARS to stay within safe context limits
    # Full text stored in evidence_submissions, not truncated at rest
    user_message = (
        f"REQUIREMENT:\n"
        f"What: {map_item.what}\n"
        f"Expected Evidence: {map_item.evidence_type}\n"
        f"Department: {map_item.department}\n"
        f"Deadline: {map_item.deadline.isoformat()}\n\n"
        f"SUBMITTED EVIDENCE:\n"
        f"File: {evidence.file_name}\n"
        f"Submitted by: {evidence.submitted_by}\n"
        f"Date: {evidence.submitted_at.isoformat()}\n\n"
        f"Evidence Content:\n"
        f"{evidence_text[:MAX_EVIDENCE_CHARS]}"
    )

    # First attempt
    try:
        verdict_data = await _call_anthropic(user_message)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "First judge LLM call failed (%s), retrying with stricter prompt…", exc
        )
        verdict_data = await _call_anthropic(user_message, retry=True)

    verdict = verdict_data["verdict"]
    reasoning = verdict_data["reasoning"]
    gaps = verdict_data.get("gaps", [])

    # Create judgment record
    judgment = Judgment(
        map_id=map_item.id,
        evidence_id=evidence.id,
        verdict=verdict,
        reasoning=reasoning,
        human_override=False,
    )
    db.add(judgment)
    await db.flush()

    # Update MAP status to reflect the verdict
    map_item.status = verdict
    await db.flush()

    # Create audit log
    output_payload = {
        "verdict": verdict,
        "reasoning": reasoning,
        "gaps": gaps,
    }
    audit = AuditLog(
        event_type="judgment_made",
        entity_type="judgment",
        entity_id=str(judgment.id),
        payload={
            "verdict": verdict,
            "reasoning": reasoning,
            "gaps": gaps,
            "evidence_id": str(evidence.id),
            "map_id": str(map_item.id),
        },
        input_hash=hash_content(evidence_text),
        output_hash=hash_content(json.dumps(output_payload, sort_keys=True)),
        model_version=settings.MODEL,
        actor="system",
    )
    db.add(audit)
    await db.flush()

    return judgment


async def override_judgment(
    judgment: Judgment,
    new_verdict: str,
    override_by: str,
    override_reason: str,
    db: AsyncSession,
) -> Judgment:
    """Apply a human override to an existing LLM judgment.

    Captures the previous verdict, transitions the MAP through an
    'under_review' state, updates the judgment with override details,
    and creates an audit trail entry.

    Args:
        judgment: The Judgment ORM object to override.
        new_verdict: The new verdict (satisfied, partial, or insufficient).
        override_by: Identifier of the person performing the override.
        override_reason: Justification for the override.
        db: Async database session.

    Returns:
        The updated Judgment ORM object.
    """
    old_verdict = judgment.verdict
    map_item = judgment.map_item

    # Transition through pending_review state
    map_item.status = "pending_review"
    await db.flush()

    # Apply override to judgment
    judgment.verdict = new_verdict
    judgment.human_override = True
    judgment.override_by = override_by
    judgment.override_reason = override_reason

    # Update MAP status to the new verdict
    map_item.status = new_verdict
    await db.flush()

    # Audit trail for the override
    audit = AuditLog(
        event_type="judgment_overridden",
        entity_type="judgment",
        entity_id=str(judgment.id),
        payload={
            "previous_verdict": old_verdict,
            "new_verdict": new_verdict,
            "override_by": override_by,
            "override_reason": override_reason,
            "map_id": str(map_item.id),
        },
        actor=override_by,
    )
    db.add(audit)
    await db.flush()

    return judgment
