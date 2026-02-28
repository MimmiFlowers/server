import os
import logging
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
from fastapi import HTTPException

logger = logging.getLogger(__name__)

ENV = os.environ.get("ENV", "dev")

if ENV == "dev":
    load_dotenv(".env.dev")
else:
    load_dotenv(".env.prod")

DB_URL = os.getenv("DB_URL")

pool: AsyncConnectionPool | None = None


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan: open the connection pool on startup, close on shutdown."""
    global pool

    if not DB_URL:
        raise RuntimeError(
            "DB_URL environment variable is not set. "
            "Cannot start without a database connection string."
        )

    pool = AsyncConnectionPool(
        conninfo=DB_URL,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pool.open()
    logger.info("Database connection pool opened (min=2, max=10)")

    yield

    await pool.close()
    logger.info("Database connection pool closed")


async def get_db_connection():
    """FastAPI dependency that provides a pooled database connection.

    The connection is automatically returned to the pool after the
    request completes, even if an exception is raised.
    """
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection pool is not available",
        )

    async with pool.connection() as conn:
        yield conn
