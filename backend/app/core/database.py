"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _build_engine_args():
    """Strip sslmode from URL (asyncpg doesn't accept it) and return (url, kwargs)."""
    url = settings.DATABASE_URL
    kwargs: dict = {}

    if "sslmode=" in url:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        ssl_mode = params.pop("sslmode", [None])[0]

        # Rebuild URL without sslmode
        remaining = {k: v[0] for k, v in params.items()}
        clean_query = urlencode(remaining) if remaining else ""
        clean_url = urlunparse(parsed._replace(query=clean_query))

        if ssl_mode:
            kwargs["connect_args"] = {"ssl": ssl_mode}

        return clean_url, kwargs

    return url, kwargs


_db_url, _engine_kwargs = _build_engine_args()

engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    **_engine_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
