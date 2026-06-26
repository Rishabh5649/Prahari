"""Routing service — keyword-based MAP routing with LLM fallback and splitting."""

import json
import logging
import re

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.models.map_item import MapItem

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    "IT-Security": [
        "encryption", "cybersecurity", "data security", "firewall",
        "access control", "penetration test", "vulnerability", "CERT",
        "incident response", "key rotation", "patch", "ISMS", "ISO 27001",
    ],
    "KYC/AML": [
        "know your customer", "KYC", "anti-money laundering", "AML",
        "CFT", "beneficial owner", "FATF", "suspicious transaction",
        "STR", "CTR", "CDD", "EDD", "PEP",
    ],
    "Retail Banking": [
        "customer onboarding", "savings account", "current account",
        "branch", "ATM", "debit card", "locker", "nomination",
        "consumer", "retail loan", "MSME",
    ],
    "Treasury": [
        "liquidity", "SLR", "CRR", "forex", "foreign exchange",
        "investment", "bond", "G-sec", "ALM", "interest rate risk",
        "capital adequacy", "CRAR",
    ],
    "Legal": [
        "regulatory filing", "board resolution", "legal opinion",
        "litigation", "penalty", "RBI Act", "Banking Regulation Act",
        "compliance certificate", "audit committee",
    ],
    "Risk": [
        "credit risk", "operational risk", "market risk", "ICAAP",
        "stress test", "NPA", "provisioning", "RAROC",
        "risk appetite", "BCM", "BCP", "disaster recovery",
    ],
}


def _score_departments(text: str) -> dict[str, int]:
    """Count keyword hits per department in the given text with word boundary matching."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            # Check for word boundaries around the keyword to avoid partial word matching
            pattern = rf"\b{re.escape(kw.lower())}\b"
            if re.search(pattern, text_lower):
                score += 1
        scores[dept] = score
    return scores


async def _llm_fallback(map_item: MapItem) -> tuple[str, str]:
    """Use Claude to determine the responsible department.

    Returns:
        Tuple of (department, reason).
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    system = (
        "You are a bank org chart specialist. Given a compliance action item, "
        'respond with ONLY a JSON object: {"department": "<one of: IT-Security, '
        'KYC/AML, Retail Banking, Treasury, Legal, Risk>", "reason": "<one '
        'sentence>"}. No preamble.'
    )

    user_msg = (
        f"Action required: {map_item.what}\n"
        f"Evidence needed: {map_item.evidence_type}\n"
        "Which bank department is responsible?"
    )

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        parsed = json.loads(raw)
        dept = parsed["department"]
        reason = parsed.get("reason", "")

        from app.models.map_item import DEPARTMENTS
        if dept not in DEPARTMENTS:
            logger.warning("LLM returned invalid department '%s', falling back to 'Legal'", dept)
            return "Legal", f"LLM returned invalid department '{dept}'. Reason: {reason}"
        
        return dept, reason
    except Exception as exc:
        logger.exception("LLM fallback routing failed for MAP %s, defaulting to Legal", map_item.id)
        return "Legal", f"LLM fallback failed: {exc}"


async def route_map(map_item: MapItem, db: AsyncSession) -> MapItem:
    """Route a single MAP to the appropriate department.

    Routing logic:
        1. Keyword scoring across all departments.
        2. Single winner → assign directly.
        3. Exact two-way tie → split into child MAPs.
        4. Zero matches everywhere → LLM fallback via Claude.
        5. pending_review MAPs retain their status (no auto-assign).

    Returns:
        The (possibly updated) MapItem.
    """
    combined_text = f"{map_item.what} {map_item.evidence_type}"
    scores = _score_departments(combined_text)
    max_score = max(scores.values())

    method = "keyword"
    was_pending = map_item.status == "pending_review"

    if max_score == 0:
        # ---- LLM fallback ----
        department, reason = await _llm_fallback(map_item)
        map_item.department = department
        method = "llm_fallback"

        fallback_audit = AuditLog(
            event_type="map_routed_llm_fallback",
            entity_type="map_item",
            entity_id=str(map_item.id),
            payload={
                "department": department,
                "reason": reason,
                "what": map_item.what,
                "evidence_type": map_item.evidence_type,
            },
            model_version=MODEL,
            actor="system",
        )
        db.add(fallback_audit)
    else:
        top_depts = [
            dept for dept, score in scores.items() if score == max_score
        ]

        if len(top_depts) == 1:
            # Clear winner
            map_item.department = top_depts[0]

        elif len(top_depts) == 2:
            # ---- Split into two child MAPs ----
            child_status = "pending_review" if was_pending else "assigned"
            if not was_pending:
                map_item.status = "assigned"

            children: list[MapItem] = []
            for dept in top_depts:
                child = MapItem(
                    circular_id=map_item.circular_id,
                    parent_map_id=map_item.id,
                    what=map_item.what,
                    deadline=map_item.deadline,
                    department=dept,
                    evidence_type=map_item.evidence_type,
                    confidence_score=map_item.confidence_score,
                    status=child_status,
                )
                db.add(child)
                children.append(child)

            await db.flush()

            split_audit = AuditLog(
                event_type="map_split",
                entity_type="map_item",
                entity_id=str(map_item.id),
                payload={
                    "child_ids": [str(c.id) for c in children],
                    "departments": top_depts,
                },
                actor="system",
            )
            db.add(split_audit)
            await db.flush()

            # Route audit for the parent (split case)
            route_audit = AuditLog(
                event_type="map_routed",
                entity_type="map_item",
                entity_id=str(map_item.id),
                payload={
                    "department": map_item.department,
                    "method": "keyword_split",
                    "keyword_scores": scores,
                    "split_departments": top_depts,
                },
                actor="system",
            )
            db.add(route_audit)
            await db.flush()

            return map_item

        else:
            # Three-or-more way tie — keep extractor's original department
            logger.info(
                "Multi-way tie (%d depts) for MAP %s, keeping extractor department '%s'",
                len(top_depts),
                map_item.id,
                map_item.department,
            )

    # ---- General routing audit log ----
    route_audit = AuditLog(
        event_type="map_routed",
        entity_type="map_item",
        entity_id=str(map_item.id),
        payload={
            "department": map_item.department,
            "method": method,
            "keyword_scores": scores,
        },
        actor="system",
    )
    db.add(route_audit)
    await db.flush()

    return map_item


async def route_all_maps(
    circular: Circular,
    maps: list[MapItem],
    db: AsyncSession,
) -> None:
    """Route every MAP from a circular to the appropriate department.

    Called automatically after extract_maps in the ingest pipeline.
    """
    for map_item in maps:
        await route_map(map_item, db)
