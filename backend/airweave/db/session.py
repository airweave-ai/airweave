"""Database session configuration."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airweave.core.config import settings

# Connection Pool Sizing Strategy:
# - With proper connection management, workers only hold DB connections for milliseconds
# - Database operations: entity lookup (~0.1s), insert/update (~0.1s)
# - Even with 100 concurrent workers, only a few need connections at the same time
# - Pool size 15 + overflow 15 = 30 total connections available
# - This efficiently handles bursts while preventing connection exhaustion
# - Multiple sync jobs can run simultaneously without issues

# Determine pool size based on worker count
worker_count = getattr(settings, "SYNC_MAX_WORKERS", 100)
# With on-demand connections: pool_size = workers * 0.15 (only 15% need DB at once)
POOL_SIZE = min(15, max(10, int(worker_count * 0.15)))
MAX_OVERFLOW = POOL_SIZE  # Allow doubling during spikes

# Connection Pool Timeout Behavior:
# - pool_timeout=30: Wait up to 30 seconds for a connection to become available
# - If all connections are busy for 30+ seconds, raises TimeoutError
# - This prevents unbounded queueing and alerts to connection leaks
#
# Alternative configurations:
# - pool_timeout=0: Don't wait at all, fail immediately if no connections
# - pool_timeout=None: Wait forever (NOT RECOMMENDED - can cause deadlocks)

# Build connect_args based on environment
connect_args_config = {
    "server_settings": {
        # Kill idle transactions after 5 minutes
        "idle_in_transaction_session_timeout": "300000",
    },
    "command_timeout": 60,
}

# Disable SSL for PgBouncer connections (internal cluster traffic)
if settings.POSTGRES_SSLMODE == "disable":
    connect_args_config["ssl"] = False

async_engine = create_async_engine(
    str(settings.SQLALCHEMY_ASYNC_DATABASE_URI),
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_timeout=30,  # Wait up to 30 seconds for a connection
    isolation_level="READ COMMITTED",
    # Note: async engines automatically use AsyncAdaptedQueuePool
    # Settings to prevent connection buildup:
    connect_args=connect_args_config,
)

AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine)


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session that can be used as a context manager.

    Yields:
        AsyncSession: An async database session

    Example:
    -------
        async with get_db_context() as db:
            await db.execute(...)

    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            try:
                await db.close()
            except Exception:
                # Connection may have been closed by server due to idle timeout; ignore on close
                pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session to be used in dependency injection.

    Yields:
    ------
        AsyncSession: An async database session

    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            try:
                await db.close()
            except Exception:
                # Connection may have been closed by server due to idle timeout; ignore on close
                pass
