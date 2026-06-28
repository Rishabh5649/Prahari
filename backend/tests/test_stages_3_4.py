"""Unit tests for Stage 3 (Routing) and Stage 4 (Evidence Intake)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.circular import Circular
from app.models.map_item import MapItem
from app.services.evidence_service import (
    check_and_escalate_overdue,
    submit_evidence,
)
from app.core.config import settings
from app.services.routing_service import route_map
from tests.conftest import run_test_in_db, run_test_with_client


def test_route_map_single_winner():
    """Test routing with a clear department keyword winner."""
    async def run(db_session):
        circular = Circular(source_hash="hash1", raw_text="IT Security rules")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Implement encryption systems",  # "encryption" is IT-Security
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Legal",  # temporary default
            evidence_type="Key rotation policy",
            confidence_score=0.9,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        routed = await route_map(map_item, db_session)
        assert routed.department == "IT-Security"
        assert routed.status == "assigned"

        # Verify audit log
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "map_routed")
        )
        audit = result.scalars().first()
        assert audit is not None
        assert audit.entity_id == str(map_item.id)
        assert audit.payload["department"] == "IT-Security"
        assert audit.payload["method"] == "keyword"

    run_test_in_db(run)


def test_route_map_two_way_tie_split():
    """Test routing exact two-way tie splits into child MAPs."""
    async def run(db_session):
        circular = Circular(source_hash="hash2", raw_text="Mixed circular")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Deploy cybersecurity savings account guidelines",  # "cybersecurity" (IT-Security), "savings account" (Retail Banking)
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Legal",
            evidence_type="Log files",
            confidence_score=0.9,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        routed = await route_map(map_item, db_session)
        assert routed.status == "assigned"

        # Verify children created
        result = await db_session.execute(
            select(MapItem).where(MapItem.parent_map_id == map_item.id)
        )
        children = result.scalars().all()
        assert len(children) == 2
        depts = {c.department for c in children}
        assert depts == {"IT-Security", "Retail Banking"}
        for child in children:
            assert child.status == "assigned"

        # Verify split audit log
        result_audit = await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "map_split")
        )
        split_audit = result_audit.scalars().first()
        assert split_audit is not None
        assert split_audit.payload["departments"] == ["IT-Security", "Retail Banking"]

    run_test_in_db(run)


@patch("app.services.routing_service.genai.Client")
def test_route_map_llm_fallback(mock_genai_client_class):
    """Test routing with no keyword matches falling back to Gemini."""
    # Setup mock GenAI client
    mock_client = MagicMock()
    mock_genai_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '{"department": "Risk", "reason": "Operational risk review required"}'
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    async def run(db_session):
        circular = Circular(source_hash="hash3", raw_text="No keywords match here")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Perform an unusual audit process",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Legal",
            evidence_type="Board minute approval",
            confidence_score=0.8,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        routed = await route_map(map_item, db_session)
        assert routed.department == "Risk"

        # Verify fallback audit log
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "map_routed_llm_fallback")
        )
        audit = result.scalars().first()
        assert audit is not None
        assert audit.payload["department"] == "Risk"
        assert audit.payload["reason"] == "Operational risk review required"

    run_test_in_db(run)


@patch("app.services.routing_service.genai.Client")
def test_route_map_three_way_tie_llm_fallback(mock_genai_client_class):
    """Test that a three-way keyword tie triggers LLM fallback routing."""
    mock_client = MagicMock()
    mock_genai_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '{"department": "Treasury", "reason": "3-way tie resolved by LLM"}'
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    async def run(db_session):
        circular = Circular(source_hash="hash3_tie", raw_text="Three way tie text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="encryption KYC ATM",  # Matches IT-Security, KYC/AML, Retail Banking (3-way tie)
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Legal",
            evidence_type="Tie break files",
            confidence_score=0.8,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        routed = await route_map(map_item, db_session)
        assert routed.department == "Treasury"

        # Verify fallback audit log
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "map_routed_llm_fallback")
        )
        audit = result.scalars().first()
        assert audit is not None
        assert audit.payload["department"] == "Treasury"
        assert audit.payload["reason"] == "Multi-way tie fallback: 3-way tie resolved by LLM"

    run_test_in_db(run)


def test_evidence_submission_success(mock_minio_client):
    """Test submitting evidence successfully updates status and calls MinIO."""
    async def run(db_session):
        circular = Circular(source_hash="hash4", raw_text="circular text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Action item",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Treasury",
            evidence_type="Report",
            confidence_score=0.9,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        file_bytes = b"pdf content"
        evidence = await submit_evidence(
            map_id=map_item.id,
            file_name="report.pdf",
            file_data=file_bytes,
            submitted_by="officer1@bank.com",
            db=db_session,
        )

        assert evidence.file_name == "report.pdf"
        assert evidence.submitted_by == "officer1@bank.com"
        assert map_item.status == "evidence_submitted"

        # Verify MinIO put_object was called
        mock_minio_client.put_object.assert_called_once()
        args, kwargs = mock_minio_client.put_object.call_args
        assert kwargs["bucket_name"] == settings.MINIO_BUCKET
        assert kwargs["object_name"].endswith("report.pdf")

        # Verify audit log
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "evidence_submitted")
        )
        audit = result.scalars().first()
        assert audit is not None
        assert audit.actor == "officer1@bank.com"

    run_test_in_db(run)


def test_check_and_escalate_overdue():
    """Test escalates past-deadline assigned MAPs to overdue."""
    async def run(db_session):
        circular = Circular(source_hash="hash5", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        # Past deadline, assigned status -> should escalate
        map1 = MapItem(
            circular_id=circular.id,
            what="Task 1",
            deadline=datetime.now(timezone.utc) - timedelta(days=1),
            department="IT-Security",
            evidence_type="Doc",
            confidence_score=0.95,
            status="assigned",
        )
        # Future deadline, assigned status -> should NOT escalate
        map2 = MapItem(
            circular_id=circular.id,
            what="Task 2",
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            department="IT-Security",
            evidence_type="Doc",
            confidence_score=0.95,
            status="assigned",
        )
        # Past deadline, satisfied status -> should NOT escalate
        map3 = MapItem(
            circular_id=circular.id,
            what="Task 3",
            deadline=datetime.now(timezone.utc) - timedelta(days=1),
            department="IT-Security",
            evidence_type="Doc",
            confidence_score=0.95,
            status="satisfied",
        )
        db_session.add_all([map1, map2, map3])
        await db_session.flush()

        count = await check_and_escalate_overdue(db_session)
        assert count == 1
        assert map1.status == "overdue"
        assert map2.status == "assigned"
        assert map3.status == "satisfied"

    run_test_in_db(run)


def test_api_list_and_detail():
    """Test API router endpoints for listing and getting MAP detail."""
    async def run(client, db_session):
        circular = Circular(source_hash="hash6", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Action item for listing",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="KYC/AML",
            evidence_type="Audit report",
            confidence_score=0.88,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        # Test GET list
        response = await client.get("/api/maps")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(m["id"] == str(map_item.id) for m in data)

        # Test GET detail
        response_detail = await client.get(f"/api/maps/{map_item.id}")
        assert response_detail.status_code == 200
        detail = response_detail.json()
        assert detail["what"] == "Action item for listing"
        assert detail["evidence_submissions"] == []

    run_test_with_client(run)


def test_api_approve_and_reject():
    """Test human approval and rejection endpoints."""
    async def run(client, db_session):
        circular = Circular(source_hash="hash7", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Action item for review",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="KYC/AML",
            evidence_type="Audit report",
            confidence_score=0.5,  # Low confidence, pending review
            status="pending_review",
        )
        db_session.add(map_item)
        await db_session.flush()

        # Test approve
        response = await client.patch(
            f"/api/maps/{map_item.id}/approve",
            json={"approved_by": "reviewer@bank.com"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "assigned"

        # Reset state to pending_review for reject test
        map_item.status = "pending_review"
        await db_session.flush()

        # Test reject
        response_reject = await client.patch(
            f"/api/maps/{map_item.id}/reject",
            json={"rejected_by": "reviewer@bank.com", "reason": "Incorrect extraction"},
        )
        assert response_reject.status_code == 200
        assert response_reject.json()["status"] == "rejected"

    run_test_with_client(run)


def test_route_map_partial_word_no_match():
    """Test that partial word matches (e.g. 'atomic' for keyword 'ATM') are ignored."""
    async def run(db_session):
        circular = Circular(source_hash="hash8", raw_text="atomic mathematics structured instructions")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Deploy atomic systems",  # Contains "atomic" which has substring "atm", and "structured" which has "str"
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
            department="Legal",
            evidence_type="Checklist",
            confidence_score=0.9,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        # Since "atm" and "str" are only subparts, they shouldn't match. It should fallback to LLM.
        # Let's mock LLM fallback to return Retail Banking
        with patch("app.services.routing_service._llm_fallback") as mock_fallback:
            mock_fallback.return_value = ("Retail Banking", "Fallback due to no boundaries")
            routed = await route_map(map_item, db_session)
            assert routed.department == "Retail Banking"
            mock_fallback.assert_called_once()

    run_test_in_db(run)


def test_api_approve_reject_cascades():
    """Test that human approval/rejection cascades to child MAPs."""
    async def run(client, db_session):
        circular = Circular(source_hash="hash9", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        parent_map = MapItem(
            circular_id=circular.id,
            what="Parent task",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="Risk",
            evidence_type="Audit report",
            confidence_score=0.5,
            status="pending_review",
        )
        db_session.add(parent_map)
        await db_session.flush()

        child_map = MapItem(
            circular_id=circular.id,
            parent_map_id=parent_map.id,
            what="Child task",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="KYC/AML",
            evidence_type="Audit report",
            confidence_score=0.5,
            status="pending_review",
        )
        db_session.add(child_map)
        await db_session.flush()

        # Approve parent -> child status should cascade
        response = await client.patch(
            f"/api/maps/{parent_map.id}/approve",
            json={"approved_by": "reviewer@bank.com"},
        )
        assert response.status_code == 200
        
        await db_session.refresh(child_map)
        assert child_map.status == "assigned"

        # Reject parent -> child status should cascade to rejected
        parent_map.status = "pending_review"
        child_map.status = "pending_review"
        await db_session.flush()

        response_reject = await client.patch(
            f"/api/maps/{parent_map.id}/reject",
            json={"rejected_by": "reviewer@bank.com", "reason": "Parent rejected"},
        )
        assert response_reject.status_code == 200
        
        await db_session.refresh(child_map)
        assert child_map.status == "rejected"

    run_test_with_client(run)


def test_api_invalid_circular_id_format():
    """Test that FastAPI returns 422 validation error for malformed circular_id."""
    async def run(client, db_session):
        response = await client.get("/api/maps?circular_id=not-a-valid-uuid")
        assert response.status_code == 422
        
    run_test_with_client(run)


def test_validate_upload_unsupported_type():
    """Test that validate_upload rejects unsupported content types with 415."""
    async def run(client, db_session):
        # Seed a map item
        circular = Circular(source_hash="hash_upload_type", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Action item for upload",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="KYC/AML",
            evidence_type="Audit report",
            confidence_score=0.88,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        # Submit an evidence upload with wrong content-type
        files = {
            "file": ("test.jpg", b"jpeg bytes", "image/jpeg")
        }
        data = {
            "map_id": str(map_item.id),
            "submitted_by": "officer1@bank.com"
        }
        response = await client.post("/api/evidence/submit", data=data, files=files)
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]

    run_test_with_client(run)


def test_validate_upload_too_large():
    """Test that validate_upload rejects files > 20MB with 413."""
    async def run(client, db_session):
        # Seed a map item
        circular = Circular(source_hash="hash_upload_large", raw_text="text")
        db_session.add(circular)
        await db_session.flush()

        map_item = MapItem(
            circular_id=circular.id,
            what="Action item for large upload",
            deadline=datetime.now(timezone.utc) + timedelta(days=10),
            department="KYC/AML",
            evidence_type="Audit report",
            confidence_score=0.88,
            status="assigned",
        )
        db_session.add(map_item)
        await db_session.flush()

        # Submit an evidence upload > 20MB
        large_bytes = b"a" * (20 * 1024 * 1024 + 1)
        files = {
            "file": ("test.pdf", large_bytes, "application/pdf")
        }
        data = {
            "map_id": str(map_item.id),
            "submitted_by": "officer1@bank.com"
        }
        response = await client.post("/api/evidence/submit", data=data, files=files)
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]

    run_test_with_client(run)

