"""
Motis Database Session
=======================
Shared async SQLAlchemy engine + session factory for the platform service.

Usage in FastAPI routes (dependency injection):
    async def my_route(db: AsyncSession = Depends(get_db)):
        result = await db.execute(...)

Usage in background tasks (direct):
    async with async_session() as session:
        await session.execute(...)

The engine is a module-level singleton — one connection pool per process.
Call init_db() at app lifespan startup to warm the pool.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

# Read DATABASE_URL from environment (pydantic-settings also provides this
# via motis_platform.settings, but we keep this module dependency-free
# so it can be imported by Alembic without pulling in the full app).
_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://motis:motis@localhost:5432/motis",
)

engine = create_async_engine(
    _DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # Verify connections before checkout
    pool_recycle=3600,           # Recycle connections every hour
    echo=False,                  # Set to True for SQL debug logging
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,      # Avoid lazy-load errors after commit
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Yields an async session, commits on success,
    rolls back on exception, always closes.

    Usage:
        @app.get("/foo")
        async def foo(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Warm up the connection pool. Call at app startup (lifespan).
    Does a SELECT 1 to verify DB connectivity and fail fast on misconfiguration.
    """
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def dispose_db() -> None:
    """
    Dispose connection pool. Call at app shutdown (lifespan).
    """
    await engine.dispose()
