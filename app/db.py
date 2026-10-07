from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

# Each process (web, bot) may hold up to 10 + 20 connections - well under Postgres' 100. The bot uses two per
# update (the handler's and the conversation log's), and a broadcast can bring hundreds of students at once.
engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=20,
                             pool_recycle=1800)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open a session, commit on success, roll back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
