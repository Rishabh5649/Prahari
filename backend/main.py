"""Prahari — FastAPI application entry point."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.dashboard import router as dashboard_router
from app.api.evidence import router as evidence_router
from app.api.ingest import router as ingest_router
from app.api.judgments import router as judgments_router
from app.api.maps import router as maps_router
from app.core.database import async_session_factory
from app.core.minio_client import ensure_bucket_exists
from app.services.evidence_service import check_and_escalate_overdue

logger = logging.getLogger(__name__)

OVERDUE_CHECK_INTERVAL = 3600  # seconds (1 hour)


async def _overdue_checker() -> None:
    """Background task that checks for overdue MAPs every hour."""
    while True:
        await asyncio.sleep(OVERDUE_CHECK_INTERVAL)
        try:
            async with async_session_factory() as session:
                count = await check_and_escalate_overdue(session)
                await session.commit()
                if count:
                    logger.info("Overdue checker: escalated %d MAP(s)", count)
        except Exception:
            logger.exception("Overdue checker failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle hook.

    Startup:
        - Ensures the MinIO evidence bucket exists.
        - Launches periodic overdue-escalation background task.
        - Tables are managed via Alembic migrations (run ``alembic upgrade head``).
    """
    # --- Startup ---
    ensure_bucket_exists()
    overdue_task = asyncio.create_task(_overdue_checker())
    yield
    # --- Shutdown ---
    overdue_task.cancel()
    try:
        await overdue_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Prahari",
    description="Agentic Compliance Intelligence for Indian Banking",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the React frontend on localhost:3000 and localhost:5173 (Vite)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(ingest_router)
app.include_router(maps_router)
app.include_router(evidence_router)
app.include_router(judgments_router)
app.include_router(audit_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok", "service": "prahari"}
