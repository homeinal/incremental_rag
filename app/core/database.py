"""Async database connection pool management"""

import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """Manages async PostgreSQL connection pool"""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get or create the connection pool"""
        if cls._pool is None:
            settings = get_settings()
            cls._pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("Database connection pool created")
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        """Close the connection pool"""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool"""
    pool = await DatabasePool.get_pool()
    async with pool.acquire() as connection:
        yield connection


async def init_db() -> None:
    """Initialize database with schema"""
    import os

    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scripts",
        "init_db.sql"
    )

    async with get_connection() as conn:
        with open(schema_path) as f:
            schema_sql = f.read()
        await conn.execute(schema_sql)
        logger.info("Database schema initialized")


async def health_check() -> bool:
    """Check database connectivity"""
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
