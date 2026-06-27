"""Stage 5 tests — Judge Agent, Judgments API, and Audit API.

Uses the same synchronous test runner pattern from conftest.py to avoid
pytest-asyncio plugin dependency issues.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import mock_minio, run_test_in_db, run_test_with_client

from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment
from app.models.map_item import MapItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_circular(db):
    """Insert a circular and return it."""
    circ = Circular(
        source_url="https://rbi.org.in/test",
        source_hash="abc123",
        raw_text="Test circular content",
        status="in_progress",
        title="Test Circular",
    )
    db.add(circ)
    return circ


def _make_map_item(db, circular, status="evidence_submitted"):
    """Insert a MAP item and return it."""
    m = MapItem(
        circular_id=circular.id,
        what="Implement encryption at rest for all customer PII",
        deadline=datetime.now(timezone.utc) + timedelta(days=90),
        department="IT-Security",
        evidence_type="Updated encryption policy document",
        confidence_score=0.95,
        status=status,
    )
    db.add(m)
    return m


def _make_evidence(db, map_item):
    """Insert an evidence submission and return it."""
    e = EvidenceSubmission(
        map_id=map_item.id,
        file_name="encryption_policy.txt",
        minio_object_key=f"evidence/{map_item.id}/{uuid.uuid4()}/encryption_policy.txt",
        submitted_by="officer@bank.com",
    )
    db.add(e)
    return e


# ---------------------------------------------------------------------------
# Test 1: Judge agent — _extract_evidence_text for .txt files
# ---------------------------------------------------------------------------

def test_extract_evidence_text_txt():
    """Text files should be decoded as UTF-8."""
    from app.agents.judge_agent import _extract_evidence_text

    async def _test(db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ)
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        # Mock MinIO response
        mock_response = MagicMock()
        mock_response.read.return_value = b"Encryption policy document content"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_minio.get_object.return_value = mock_response

        text = await _extract_evidence_text(e)
        assert text == "Encryption policy document content"
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    run_test_in_db(_test)


# ---------------------------------------------------------------------------
# Test 2: Judge agent — _extract_evidence_text for binary files
# ---------------------------------------------------------------------------

def test_extract_evidence_text_binary():
    """Binary files should return a placeholder description."""
    from app.agents.judge_agent import _extract_evidence_text

    async def _test(db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ)
        await db.flush()

        e = EvidenceSubmission(
            map_id=m.id,
            file_name="screenshot.png",
            minio_object_key=f"evidence/{m.id}/screenshot.png",
            submitted_by="officer@bank.com",
        )
        db.add(e)
        await db.flush()

        mock_response = MagicMock()
        mock_response.read.return_value = b"\x89PNG\x0d\x0a\x1a\x0a" + b"\x00" * 100
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_minio.get_object.return_value = mock_response

        text = await _extract_evidence_text(e)
        assert "[Binary file: screenshot.png" in text

    run_test_in_db(_test)


# ---------------------------------------------------------------------------
# Test 3: Judge agent — judge_evidence creates judgment + audit log
# ---------------------------------------------------------------------------

def test_judge_evidence_creates_judgment():
    """judge_evidence should create a Judgment, update MAP status, and log to audit."""
    from app.agents.judge_agent import judge_evidence

    mock_llm_response = {
        "verdict": "satisfied",
        "reasoning": "The encryption policy covers all customer PII at rest.",
        "gaps": [],
    }

    async def _test(db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ)
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        # Mock MinIO for text extraction
        mock_response = MagicMock()
        mock_response.read.return_value = b"Full encryption policy content"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_minio.get_object.return_value = mock_response

        with patch("app.agents.judge_agent._call_anthropic", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = mock_llm_response
            judgment = await judge_evidence(m, e, db)

        assert judgment.verdict == "satisfied"
        assert judgment.reasoning == mock_llm_response["reasoning"]
        assert judgment.human_override is False
        assert judgment.map_id == m.id
        assert judgment.evidence_id == e.id

        # MAP status should be updated to the verdict
        assert m.status == "satisfied"

        # Audit log should exist
        from sqlalchemy import select
        result = await db.execute(
            select(AuditLog).where(AuditLog.event_type == "judgment_made")
        )
        audit = result.scalar_one()
        assert audit.entity_type == "judgment"
        assert audit.model_version == "claude-3-5-sonnet-20240620"
        payload = audit.payload
        assert payload["verdict"] == "satisfied"
        assert payload["evidence_id"] == str(e.id)

    run_test_in_db(_test)


# ---------------------------------------------------------------------------
# Test 4: Judge agent — override_judgment
# ---------------------------------------------------------------------------

def test_override_judgment():
    """override_judgment should change verdict, set human_override, and create audit."""
    from app.agents.judge_agent import override_judgment

    async def _test(db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ, status="satisfied")
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        judgment = Judgment(
            map_id=m.id,
            evidence_id=e.id,
            verdict="satisfied",
            reasoning="Initially satisfied.",
            human_override=False,
        )
        db.add(judgment)
        await db.flush()

        updated = await override_judgment(
            judgment, "partial", "auditor@bank.com", "Missing implementation evidence", db
        )

        assert updated.verdict == "partial"
        assert updated.human_override is True
        assert updated.override_by == "auditor@bank.com"
        assert updated.override_reason == "Missing implementation evidence"

        # MAP status should reflect new verdict
        assert m.status == "partial"

        # Audit log for override
        from sqlalchemy import select
        result = await db.execute(
            select(AuditLog).where(AuditLog.event_type == "judgment_overridden")
        )
        audit = result.scalar_one()
        assert audit.payload["previous_verdict"] == "satisfied"
        assert audit.payload["new_verdict"] == "partial"
        assert audit.actor == "auditor@bank.com"

    run_test_in_db(_test)


# ---------------------------------------------------------------------------
# Test 5: Judgments API — POST /judge (happy path)
# ---------------------------------------------------------------------------

def test_api_judge_happy_path():
    """POST /api/judgments/{map_id}/judge should return 200 with a judgment."""
    mock_llm_response = {
        "verdict": "partial",
        "reasoning": "Policy exists but lacks implementation timeline.",
        "gaps": ["No implementation timeline", "No encryption algorithm specified"],
    }

    async def _test(client, db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ, status="evidence_submitted")
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        # Mock MinIO
        mock_response = MagicMock()
        mock_response.read.return_value = b"Policy document content"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_minio.get_object.return_value = mock_response

        with patch("app.agents.judge_agent._call_anthropic", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = mock_llm_response
            resp = await client.post(
                f"/api/judgments/{m.id}/judge",
                json={"evidence_id": str(e.id)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "partial"
        assert data["human_override"] is False

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 6: Judgments API — POST /judge rejects wrong status
# ---------------------------------------------------------------------------

def test_api_judge_wrong_status():
    """POST /judge should return 400 if MAP is not in evidence_submitted status."""

    async def _test(client, db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ, status="assigned")
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        resp = await client.post(
            f"/api/judgments/{m.id}/judge",
            json={"evidence_id": str(e.id)},
        )
        assert resp.status_code == 400
        assert "evidence" in resp.json()["detail"].lower()

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 7: Judgments API — POST /override
# ---------------------------------------------------------------------------

def test_api_override():
    """POST /api/judgments/{id}/override should update the judgment."""

    async def _test(client, db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ, status="partial")
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        j = Judgment(
            map_id=m.id,
            evidence_id=e.id,
            verdict="partial",
            reasoning="Some gaps found.",
            human_override=False,
        )
        db.add(j)
        await db.flush()

        resp = await client.post(
            f"/api/judgments/{j.id}/override",
            json={
                "new_verdict": "satisfied",
                "override_by": "cco@bank.com",
                "override_reason": "Gaps have been filled offline",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "satisfied"
        assert data["human_override"] is True
        assert data["override_by"] == "cco@bank.com"

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 8: Judgments API — POST /override with invalid verdict
# ---------------------------------------------------------------------------

def test_api_override_invalid_verdict():
    """POST /override with invalid verdict should return 400."""

    async def _test(client, db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ)
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        j = Judgment(
            map_id=m.id,
            evidence_id=e.id,
            verdict="partial",
            reasoning="Test.",
            human_override=False,
        )
        db.add(j)
        await db.flush()

        resp = await client.post(
            f"/api/judgments/{j.id}/override",
            json={
                "new_verdict": "approved",
                "override_by": "admin",
                "override_reason": "reason",
            },
        )
        assert resp.status_code == 400

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 9: Judgments API — GET /{map_id} returns judgments
# ---------------------------------------------------------------------------

def test_api_get_judgments():
    """GET /api/judgments/{map_id} should return all judgments for a MAP."""

    async def _test(client, db):
        circ = _make_circular(db)
        await db.flush()
        m = _make_map_item(db, circ)
        await db.flush()
        e = _make_evidence(db, m)
        await db.flush()

        for verdict in ["partial", "satisfied"]:
            j = Judgment(
                map_id=m.id,
                evidence_id=e.id,
                verdict=verdict,
                reasoning=f"Verdict: {verdict}",
                human_override=False,
            )
            db.add(j)
        await db.flush()

        resp = await client.get(f"/api/judgments/{m.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 10: Audit API — GET /api/audit (paginated)
# ---------------------------------------------------------------------------

def test_api_audit_paginated():
    """GET /api/audit should return paginated audit log entries."""

    async def _test(client, db):
        # Insert some audit log entries
        for i in range(5):
            audit = AuditLog(
                event_type="test_event",
                entity_type="test_entity",
                entity_id=str(uuid.uuid4()),
                payload={"index": i},
                actor="system",
            )
            db.add(audit)
        await db.flush()

        resp = await client.get("/api/audit?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["items"]) == 3
        assert data["total_pages"] == 2

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 11: Audit API — GET /api/audit with filters
# ---------------------------------------------------------------------------

def test_api_audit_filter_by_event_type():
    """GET /api/audit?event_type=... should filter results."""

    async def _test(client, db):
        for event_type in ["judgment_made", "evidence_submitted", "judgment_made"]:
            audit = AuditLog(
                event_type=event_type,
                entity_type="test",
                entity_id=str(uuid.uuid4()),
                payload={"data": "test"},
                actor="system",
            )
            db.add(audit)
        await db.flush()

        resp = await client.get("/api/audit?event_type=judgment_made")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(item["event_type"] == "judgment_made" for item in data["items"])

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 12: Audit API — GET /api/audit/export CSV
# ---------------------------------------------------------------------------

def test_api_audit_export_csv():
    """GET /api/audit/export should return a CSV file."""

    async def _test(client, db):
        audit = AuditLog(
            event_type="judgment_made",
            entity_type="judgment",
            entity_id="test-id",
            payload={"verdict": "satisfied"},
            input_hash="abc",
            output_hash="def",
            model_version="claude-3-5-sonnet-20240620",
            actor="system",
        )
        db.add(audit)
        await db.flush()

        resp = await client.get("/api/audit/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "audit_log_export.csv" in resp.headers.get("content-disposition", "")

        lines = resp.text.strip().split("\n")
        assert len(lines) >= 2  # header + at least 1 data row
        header = lines[0]
        assert "event_type" in header
        assert "payload" in header

    run_test_with_client(_test)
