import pytest
from unittest.mock import patch, MagicMock
from app.services.ingest_service import ingest_from_url
from app.agents.extractor_agent import extract_maps
from app.models.circular import Circular
from app.models.map_item import MapItem
from app.models.audit_log import AuditLog
from tests.conftest import run_test_in_db

# Mock for extract_title to avoid complex text processing
@patch("app.services.ingest_service.extract_title", return_value="Test Title")
@patch("app.services.ingest_service.parse_url")
def test_duplicate_detection(mock_parse_url, mock_extract_title):
    async def async_test(session):
        mock_parse_url.return_value = "Same regulatory text content"
        url = "http://example.com/circular.pdf"
        
        # First call
        await ingest_from_url(url, session)
        await session.commit()
        
        # Second call with same content should raise ValueError
        with pytest.raises(ValueError, match="Duplicate circular"):
            await ingest_from_url(url, session)
            
    run_test_in_db(async_test)

@patch("app.agents.extractor_agent._call_gemini")
def test_extractor_agent(mock_gemini):
    async def async_test(session):
        # Mock LLM response
        mock_gemini.return_value = [
            {
                "what": "Requirement 1",
                "deadline_text": "by 31 Dec 2025",
                "department": "IT-Security",
                "evidence_type": "Policy doc",
                "confidence_score": 0.9
            },
            {
                "what": "Requirement 2",
                "deadline_text": "immediately",
                "department": "Risk",
                "evidence_type": "Log export",
                "confidence_score": 0.8
            }
        ]
        
        # Create a circular
        circular = Circular(
            source_url="http://test.com",
            source_hash="hash123",
            raw_text="Extracted text from doc",
            status="processing"
        )
        session.add(circular)
        await session.flush()
        
        # Call extractor
        maps = await extract_maps(circular, session)
        
        # Assertions
        assert len(maps) == 2
        assert maps[0].what == "Requirement 1"
        assert maps[1].what == "Requirement 2"
        
        # Check AuditLog
        from sqlalchemy import select
        result = await session.execute(
            select(AuditLog).where(AuditLog.event_type == "extraction_complete")
        )
        audit = result.scalar_one_or_none()
        assert audit is not None
        assert audit.payload["total_maps"] == 2
        
    run_test_in_db(async_test)
