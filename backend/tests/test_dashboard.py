"""Dashboard API tests — circulars summary, detail, department view, system stats.

Uses the same synchronous test runner pattern from conftest.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

from conftest import run_test_with_client

from app.models.circular import Circular
from app.models.evidence import EvidenceSubmission
from app.models.judgment import Judgment
from app.models.map_item import MapItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_data(db):
    """Seed a circular with diverse MAP statuses and return IDs."""
    circ_id = uuid.uuid4()
    circ = Circular(
        id=circ_id,
        source_url="https://rbi.org.in/test-dashboard",
        source_hash="dashboardhash123",
        raw_text="Dashboard test circular content",
        status="in_progress",
        title="RBI Dashboard Test Circular",
    )
    db.add(circ)

    now = datetime.now(timezone.utc)
    maps = []
    statuses = [
        ("satisfied", "IT-Security", -10),      # deadline passed, satisfied
        ("assigned", "KYC/AML", 30),             # in-progress
        ("pending_review", "Treasury", 60),      # pending
        ("overdue", "Legal", -5),                # overdue
        ("evidence_submitted", "IT-Security", 20),  # in-progress
    ]
    for status, dept, days_offset in statuses:
        m = MapItem(
            circular_id=circ_id,
            what=f"Test MAP ({status})",
            deadline=now + timedelta(days=days_offset),
            department=dept,
            evidence_type="Test evidence",
            confidence_score=0.9,
            status=status,
        )
        db.add(m)
        maps.append(m)

    return circ, maps



# ---------------------------------------------------------------------------
# Test 1: GET /api/dashboard/circulars — aggregated stats
# ---------------------------------------------------------------------------

def test_dashboard_circulars_list():
    """GET /api/dashboard/circulars returns circulars with aggregated MAP stats."""

    async def _test(client, db):
        circ, maps = _seed_data(db)
        await db.flush()

        resp = await client.get("/api/dashboard/circulars")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        item = data[0]
        assert item["id"] == str(circ.id)
        assert item["title"] == "RBI Dashboard Test Circular"
        assert item["total_maps"] == 5
        assert item["maps_satisfied"] == 1
        assert item["maps_pending_review"] == 1
        assert item["maps_overdue"] == 1
        # in-progress: assigned + evidence_submitted = 2
        assert item["maps_in_progress"] == 2
        # days_to_nearest_deadline should be set (the nearest open MAP deadline)
        assert item["days_to_nearest_deadline"] is not None

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 2: GET /api/dashboard/circulars — empty database
# ---------------------------------------------------------------------------

def test_dashboard_circulars_empty():
    """GET /api/dashboard/circulars returns empty list when no circulars exist."""

    async def _test(client, db):
        resp = await client.get("/api/dashboard/circulars")
        assert resp.status_code == 200
        assert resp.json() == []

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 3: GET /api/dashboard/circulars/{id} — circular detail
# ---------------------------------------------------------------------------

def test_dashboard_circular_detail():
    """GET /api/dashboard/circulars/{id} returns full detail with MAPs."""

    async def _test(client, db):
        circ, maps = _seed_data(db)
        await db.flush()

        # Add evidence and judgment to first MAP
        e = EvidenceSubmission(
            map_id=maps[0].id,
            file_name="policy.pdf",
            minio_object_key=f"evidence/{maps[0].id}/policy.pdf",
            submitted_by="officer@bank.com",
        )
        db.add(e)
        await db.flush()

        j = Judgment(
            map_id=maps[0].id,
            evidence_id=e.id,
            verdict="satisfied",
            reasoning="Fully compliant.",
            human_override=False,
        )
        db.add(j)
        await db.flush()

        resp = await client.get(f"/api/dashboard/circulars/{circ.id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == str(circ.id)
        assert data["title"] == "RBI Dashboard Test Circular"
        assert data["raw_text"] == "Dashboard test circular content"
        assert len(data["maps"]) == 5

        # Find the MAP that has judgment/evidence
        enriched = [m for m in data["maps"] if m["latest_judgment"] is not None]
        assert len(enriched) == 1
        assert enriched[0]["latest_judgment"]["verdict"] == "satisfied"
        assert enriched[0]["latest_evidence"]["file_name"] == "policy.pdf"

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 4: GET /api/dashboard/circulars/{id} — 404 for missing circular
# ---------------------------------------------------------------------------

def test_dashboard_circular_detail_not_found():
    """GET /api/dashboard/circulars/{id} returns 404 for nonexistent circular."""

    async def _test(client, db):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/dashboard/circulars/{fake_id}")
        assert resp.status_code == 404

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 5: GET /api/dashboard/department/{dept} — valid department
# ---------------------------------------------------------------------------

def test_dashboard_department_view():
    """GET /api/dashboard/department/{dept} returns MAPs for that department."""

    async def _test(client, db):
        circ, maps = _seed_data(db)
        await db.flush()

        resp = await client.get("/api/dashboard/department/IT-Security")
        assert resp.status_code == 200
        data = resp.json()
        # We seeded 2 IT-Security MAPs
        assert len(data) == 2
        # All should be IT-Security
        for item in data:
            assert item["department"] == "IT-Security"

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 6: GET /api/dashboard/department/{dept} — overdue ordering
# ---------------------------------------------------------------------------

def test_dashboard_department_overdue_first():
    """Overdue MAPs should appear before non-overdue MAPs."""

    async def _test(client, db):
        circ = Circular(
            source_url="https://rbi.org.in/overdue-test",
            source_hash="overduetest",
            raw_text="Overdue ordering test",
            status="in_progress",
            title="Overdue Test",
        )
        db.add(circ)
        await db.flush()

        now = datetime.now(timezone.utc)
        # Non-overdue with earlier deadline
        m1 = MapItem(
            circular_id=circ.id, what="Non-overdue", deadline=now + timedelta(days=5),
            department="Legal", evidence_type="Test", confidence_score=0.9, status="assigned",
        )
        # Overdue with later deadline
        m2 = MapItem(
            circular_id=circ.id, what="Overdue", deadline=now + timedelta(days=30),
            department="Legal", evidence_type="Test", confidence_score=0.9, status="overdue",
        )
        db.add_all([m1, m2])
        await db.flush()

        resp = await client.get("/api/dashboard/department/Legal")
        assert resp.status_code == 200
        data = resp.json()
        # Overdue should come first despite later deadline
        assert data[0]["status"] == "overdue"
        assert data[1]["status"] == "assigned"

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 7: GET /api/dashboard/department/{dept} — invalid department
# ---------------------------------------------------------------------------

def test_dashboard_department_invalid():
    """GET /api/dashboard/department/{dept} returns 422 for invalid department."""

    async def _test(client, db):
        resp = await client.get("/api/dashboard/department/InvalidDept")
        assert resp.status_code == 422

    run_test_with_client(_test)


# ---------------------------------------------------------------------------
# Test 8: GET /api/dashboard/stats — system statistics
# ---------------------------------------------------------------------------

def test_dashboard_stats():
    """GET /api/dashboard/stats returns correct aggregate counts."""

    async def _test(client, db):
        # Seed 2 circulars
        c1 = Circular(
            source_hash="stats1", raw_text="C1", status="compliant", title="C1",
        )
        c2 = Circular(
            source_hash="stats2", raw_text="C2", status="overdue", title="C2",
        )
        db.add_all([c1, c2])
        await db.flush()

        now = datetime.now(timezone.utc)
        m1 = MapItem(
            circular_id=c1.id, what="M1", deadline=now + timedelta(days=30),
            department="Risk", evidence_type="T", confidence_score=0.9, status="satisfied",
        )
        m2 = MapItem(
            circular_id=c1.id, what="M2", deadline=now + timedelta(days=30),
            department="Risk", evidence_type="T", confidence_score=0.9, status="pending_review",
        )
        m3 = MapItem(
            circular_id=c2.id, what="M3", deadline=now - timedelta(days=5),
            department="Legal", evidence_type="T", confidence_score=0.9, status="overdue",
        )
        db.add_all([m1, m2, m3])
        await db.flush()

        resp = await client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_circulars"] == 2
        assert data["compliant_circulars"] == 1
        assert data["overdue_circulars"] == 1
        assert data["total_maps"] == 3
        assert data["maps_pending_review"] == 1
        assert data["maps_satisfied"] == 1
        assert data["maps_overdue"] == 1

    run_test_with_client(_test)
