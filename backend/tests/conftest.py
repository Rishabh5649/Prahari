"""Pytest configuration and helpers without pytest-asyncio dependency."""

import asyncio
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy import BigInteger

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 1. Mock minio_client and anthropic BEFORE importing any app code
import app.core.minio_client
mock_minio = MagicMock()

# Patch MinIO client and direct client initialisation
patcher_minio = patch("app.core.minio_client.minio_client", mock_minio)
patcher_minio_ensure = patch("app.core.minio_client.ensure_bucket_exists", MagicMock())
patcher_minio.start()
patcher_minio_ensure.start()

# Override environment variables for config loading
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "mock"
os.environ["MINIO_SECRET_KEY"] = "mock"
os.environ["MINIO_BUCKET"] = "mock-bucket"

# Import app code
from app.core.database import Base, get_db
from main import app


@pytest.fixture
def mock_minio_client():
    """Fixture to access the mocked MinIO client and reset it."""
    mock_minio.reset_mock()
    return mock_minio


def run_test_in_db(test_coro):
    """Run an async test with a clean SQLite in-memory database."""
    async def wrapper():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            try:
                await test_coro(session)
            finally:
                await session.rollback()
                
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(wrapper())


def run_test_with_client(test_coro):
    """Run an async API test with TestClient and SQLite database."""
    async def wrapper():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            async def _get_db_override():
                yield session

            app.dependency_overrides[get_db] = _get_db_override
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                try:
                    await test_coro(client, session)
                finally:
                    app.dependency_overrides.clear()
                    await session.rollback()
                    
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(wrapper())
