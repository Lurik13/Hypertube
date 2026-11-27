"""Database engines and the request-scoped session dependency.

psycopg 3 serves both engines from the same DATABASE_URL: async for the API,
sync for Alembic, the Celery worker and scripts.
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

async_engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


@lru_cache
def get_sync_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)
