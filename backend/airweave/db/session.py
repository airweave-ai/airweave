"""Database session configuration."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airweave.core.config import settings

# Connection Pool Sizing Strategy (PgBouncer-aware):
# - PgBouncer handles connection pooling to PostgreSQL (2000 client → 300 DB connections)
# - Production: 6 worker pods × 60 connections = 360 total (120% of backend pool capacity)
# - SQLAlchemy pool sized for per-pod concurrency, not total system capacity
# - During batch processing, workers can hold 2-3 connections simultaneously:
#   1. ActionResolver bulk entity hash lookup
#   2. EntityPostgresHandler batch insert/update/delete
#   3. GuardRailService usage flush (every 100 entities)
# - Base pool = worker count, overflow = 2× workers for peak concurrent DB operations
# - Example: 20 workers → 20 base + 40 overflow = 60 total connections per pod

POOL_SIZE = settings.db_pool_size
MAX_OVERFLOW = settings.db_pool_max_overflow

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

# Dedicated engine for health checks — isolated from the application pool so that
# a fully-saturated app pool cannot cause the readiness probe to false-negative.
health_check_engine = create_async_engine(
    str(settings.SQLALCHEMY_ASYNC_DATABASE_URI),
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,
    connect_args=connect_args_config,
)


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
