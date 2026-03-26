"""CRUD operations for the APIKey model."""

import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, cast
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import ConflictException, NotFoundException, PermissionException
from airweave.core.logging import logger
from airweave.core.shared_models import ApiKeyStatus
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.models.api_key_usage_log import APIKeyUsageLog
from airweave.schemas import APIKeyCreate, APIKeyUpdate
from airweave.schemas.api_key import APIKeyUsageStats


def _hash_key(key: str) -> str:
    """HMAC-SHA256 hash of an API key, keyed by ENCRYPTION_KEY.

    Keys are 256-bit entropy (secrets.token_urlsafe(32)); the 8-char
    key_prefix leaks ~48 bits, leaving ~208 bits — brute-force is
    infeasible through any hash.  HMAC keying adds defense-in-depth
    so stored hashes are useless without ENCRYPTION_KEY.
    """
    return hmac.new(
        settings.ENCRYPTION_KEY.encode(),
        key.encode(),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class UsageEvent:
    """A single API key usage event buffered for batch insertion."""

    key_id: UUID
    organization_id: UUID
    ip_address: str
    endpoint: str
    user_agent: Optional[str]
    timestamp: datetime


class UsageBuffer:
    """Buffers API key usage events and flushes them in batches.

    Events are enqueued without touching the database. A background
    task drains the queue every ``flush_interval`` seconds or when
    ``batch_size`` events accumulate, whichever comes first. Each
    flush opens a single DB session, bulk-inserts log rows, and
    issues one deduplicated UPDATE per key for ``last_used_date``
    and ``last_used_ip``.
    """

    def __init__(self, flush_interval: int = 5, batch_size: int = 500) -> None:
        """Create a buffer that flushes every *flush_interval* seconds or *batch_size* events."""
        self._queue: asyncio.Queue[UsageEvent] = asyncio.Queue()
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._task: Optional[asyncio.Task[None]] = None
        self._batch_ready = asyncio.Event()
        self._started = False
        self._warned = False

    def enqueue(self, event: UsageEvent) -> None:
        """Add a usage event to the buffer (non-blocking, no DB)."""
        if not self._started:
            if not self._warned:
                logger.warning("UsageBuffer.enqueue() called before start()")
                self._warned = True
        self._queue.put_nowait(event)
        if self._queue.qsize() >= self._batch_size:
            self._batch_ready.set()

    async def start(self) -> None:
        """Start the background flush loop."""
        self._started = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Flush remaining events and cancel the background task."""
        self._started = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._flush()

    async def _run(self) -> None:
        """Drain the queue on interval or batch-size threshold."""
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        self._wait_for_batch(),
                        timeout=self._flush_interval,
                    )
                except asyncio.TimeoutError:
                    pass  # Expected: timeout triggers periodic flush
                await self._flush()
        except asyncio.CancelledError:
            return  # Graceful shutdown; remaining events flushed in stop()

    async def _wait_for_batch(self) -> None:
        """Block until the queue reaches batch_size."""
        await self._batch_ready.wait()
        self._batch_ready.clear()

    async def _flush(self) -> None:
        """Drain the queue and write all buffered events in one session."""
        events: list[UsageEvent] = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if not events:
            return

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await self._write_events(events)
                return
            except OperationalError:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                else:
                    logger.error(
                        "API key usage events dropped after retries",
                        dropped_count=len(events),
                        max_attempts=max_attempts,
                    )
            except Exception as exc:
                logger.error(
                    "API key usage events dropped during flush",
                    dropped_count=len(events),
                    error=str(exc),
                )
                return

    async def _write_events(self, events: list[UsageEvent]) -> None:
        """Bulk-insert log rows and update last-used metadata."""
        async with get_db_context() as db:
            await db.execute(
                insert(APIKeyUsageLog),
                [
                    {
                        "api_key_id": e.key_id,
                        "organization_id": e.organization_id,
                        "timestamp": e.timestamp,
                        "ip_address": e.ip_address,
                        "endpoint": e.endpoint,
                        "user_agent": e.user_agent,
                    }
                    for e in events
                ],
            )

            # Deduplicated UPDATE: keep only latest event per key
            latest: dict[UUID, UsageEvent] = {}
            for e in events:
                prev = latest.get(e.key_id)
                if prev is None or e.timestamp > prev.timestamp:
                    latest[e.key_id] = e

            for e in latest.values():
                await db.execute(
                    update(APIKey)
                    .where(APIKey.id == e.key_id)
                    .values(
                        last_used_date=e.timestamp,
                        last_used_ip=e.ip_address,
                    )
                )

            await db.commit()


class CRUDAPIKey(CRUDBaseOrganization[APIKey, APIKeyCreate, APIKeyUpdate]):
    """CRUD operations for the APIKey model."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            ctx (BaseContext): The API context.
            uow (Optional[UnitOfWork]): The unit of work to use for
                the transaction.

        Returns:
        -------
            APIKey: The created API key.

        """
        key = secrets.token_urlsafe(32)
        encrypted_key = credentials.encrypt({"key": key})
        key_hash = _hash_key(key)

        expiration_days = obj_in.expiration_days if obj_in.expiration_days is not None else 90
        expiration_date = utc_now_naive() + timedelta(days=expiration_days)

        api_key_data = {
            "encrypted_key": encrypted_key,
            "expiration_date": expiration_date,
            "status": ApiKeyStatus.ACTIVE.value,
            "key_prefix": key[:8],
            "key_hash": key_hash,
            "description": obj_in.description,
        }

        return await super().create(
            db=db,
            obj_in=api_key_data,
            ctx=ctx,
            uow=uow,
            skip_validation=True,
        )

    async def get_all_for_ctx(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIKey]:
        """Get all API keys for an API context's organization.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (BaseContext): The API context.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
        -------
            list[APIKey]: A list of API keys for the organization.

        """
        return await self.get_multi(
            db=db,
            ctx=ctx,
            skip=skip,
            limit=limit,
        )

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Optional[APIKey]:
        """Look up an API key by its HMAC-SHA256 hash (O(1) indexed lookup).

        Rejects expired or revoked keys immediately. Uses the indexed
        ``key_hash`` column for constant-time lookup, then verifies
        the decrypted key via constant-time comparison.

        Args:
        ----
            db (AsyncSession): The database session.
            key (str): The plain API key to validate.

        Returns:
        -------
            Optional[APIKey]: The API key if found and valid.

        Raises:
        ------
            NotFoundException: If no matching API key is found.
            PermissionException: If the key has expired or been revoked.

        """
        key_hash = _hash_key(key)
        query = select(self.model).where(self.model.key_hash == key_hash)
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise NotFoundException("API key not found")

        # Belt-and-suspenders: decrypt and verify the key matches
        try:
            decrypted_data = credentials.decrypt(api_key.encrypted_key)
            stored_key = decrypted_data.get("key") if isinstance(decrypted_data, dict) else None
            if not isinstance(stored_key, str) or not hmac.compare_digest(stored_key, key):
                raise NotFoundException("API key not found")
        except (InvalidToken, ValueError):
            raise NotFoundException("API key not found")

        now = utc_now_naive()

        if api_key.status in (ApiKeyStatus.EXPIRED.value, ApiKeyStatus.REVOKED.value):
            raise PermissionException("API key is not active")

        if api_key.expiration_date < now:
            raise PermissionException("API key is not active")

        return api_key

    async def revoke(
        self,
        db: AsyncSession,
        *,
        api_key_id: UUID,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Revoke an active key immediately.

        Uses a WHERE ``status='active'`` guard to prevent concurrent
        revocation races.

        Args:
        ----
            db (AsyncSession): The database session.
            api_key_id (UUID): The ID of the key to revoke.
            uow (Optional[UnitOfWork]): Unit of work; when provided,
                the caller is responsible for committing.

        Returns:
        -------
            APIKey: The refreshed API key with revoked status.

        Raises:
        ------
            ConflictException: If the key is not active (already
                revoked or expired).
            NotFoundException: If the key disappears after update.

        """
        now = utc_now_naive()
        stmt = (
            update(self.model)
            .where(self.model.id == api_key_id)
            .where(self.model.status == ApiKeyStatus.ACTIVE.value)
            .values(
                status=ApiKeyStatus.REVOKED.value,
                revoked_at=now,
                modified_at=now,
            )
        )
        result = cast(CursorResult[Any], await db.execute(stmt))

        if result.rowcount == 0:
            raise ConflictException("API key is not active (already revoked or expired)")

        if uow:
            await db.flush()
        else:
            await db.commit()

        refreshed = await db.get(self.model, api_key_id)
        if refreshed is None:
            raise NotFoundException(
                f"API key {api_key_id} not found after revocation"
            )
        return refreshed

    def record_usage(
        self,
        *,
        api_key_obj: APIKey,
        ip_address: str,
        endpoint: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Enqueue a usage event for batch insertion.

        The event is buffered in-memory and flushed periodically by
        the ``UsageBuffer`` background task — no DB work happens here.

        Args:
        ----
            api_key_obj (APIKey): The API key being used.
            ip_address (str): The client IP address.
            endpoint (str): The endpoint path being accessed.
            user_agent (Optional[str]): The client User-Agent header.

        """
        usage_buffer.enqueue(
            UsageEvent(
                key_id=cast(UUID, api_key_obj.id),
                organization_id=api_key_obj.organization_id,
                ip_address=ip_address,
                endpoint=endpoint,
                user_agent=user_agent,
                timestamp=utc_now_naive(),
            )
        )

    def record_usage_by_id(
        self,
        *,
        api_key_id: UUID,
        organization_id: UUID,
        ip_address: str,
        endpoint: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Enqueue a usage event from cached auth metadata.

        Same as record_usage but accepts raw IDs instead of an ORM
        object, so it can be called on the cache-hit path without a
        database lookup.
        """
        usage_buffer.enqueue(
            UsageEvent(
                key_id=api_key_id,
                organization_id=organization_id,
                ip_address=ip_address,
                endpoint=endpoint,
                user_agent=user_agent,
                timestamp=utc_now_naive(),
            )
        )

    async def get_usage_log(
        self,
        db: AsyncSession,
        *,
        api_key_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[APIKeyUsageLog]:
        """Return paginated usage log entries for a key, most recent first.

        Args:
        ----
            db (AsyncSession): The database session.
            api_key_id (UUID): The ID of the API key.
            skip (int): Number of records to skip.
            limit (int): Maximum number of records to return.

        Returns:
        -------
            list[APIKeyUsageLog]: Usage log entries ordered by
                timestamp descending.

        """
        query = (
            select(APIKeyUsageLog)
            .where(APIKeyUsageLog.api_key_id == api_key_id)
            .order_by(APIKeyUsageLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_usage_stats(
        self,
        db: AsyncSession,
        *,
        api_key_id: UUID,
    ) -> APIKeyUsageStats:
        """Return aggregate usage stats for a key.

        Args:
        ----
            db (AsyncSession): The database session.
            api_key_id (UUID): The ID of the API key.

        Returns:
        -------
            APIKeyUsageStats: Aggregated statistics including total
                requests, unique IPs, and unique endpoints.

        """
        query = select(
            func.count().label("total_requests"),
            func.min(APIKeyUsageLog.timestamp).label("first_used"),
            func.max(APIKeyUsageLog.timestamp).label("last_used"),
            func.count(func.distinct(APIKeyUsageLog.ip_address)).label("unique_ips"),
            func.count(func.distinct(APIKeyUsageLog.endpoint)).label("unique_endpoints"),
        ).where(APIKeyUsageLog.api_key_id == api_key_id)

        result = await db.execute(query)
        row = result.one()
        return APIKeyUsageStats(
            api_key_id=api_key_id,
            total_requests=row.total_requests,
            first_used=row.first_used,
            last_used=row.last_used,
            unique_ips=row.unique_ips,
            unique_endpoints=row.unique_endpoints,
        )

    async def get_revoked_keys_older_than(
        self,
        db: AsyncSession,
        *,
        max_age_days: int = 90,
    ) -> list[APIKey]:
        """Return revoked keys older than the retention period.

        Args:
        ----
            db (AsyncSession): The database session.
            max_age_days (int): Retention period in days (default 90).

        Returns:
        -------
            list[APIKey]: Revoked keys whose ``revoked_at`` is older
                than the cutoff.

        """
        cutoff = utc_now_naive() - timedelta(days=max_age_days)
        query = select(self.model).where(
            self.model.status == ApiKeyStatus.REVOKED.value,
            self.model.revoked_at < cutoff,
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def expire_past_due_keys(self, db: AsyncSession) -> int:
        """Transition active keys past their expiration_date to expired.

        Caller is responsible for committing the transaction.

        Args:
        ----
            db (AsyncSession): The database session.

        Returns:
        -------
            int: The number of keys transitioned to expired status.

        """
        now = utc_now_naive()
        stmt = (
            update(self.model)
            .where(
                self.model.status == ApiKeyStatus.ACTIVE.value,
                self.model.expiration_date < now,
            )
            .values(status=ApiKeyStatus.EXPIRED.value, modified_at=now)
        )
        result = cast(CursorResult[Any], await db.execute(stmt))
        return result.rowcount

    async def prune_usage_log(
        self, db: AsyncSession, *, max_age_days: int = 90, batch_size: int = 10_000,
    ) -> int:
        """Delete usage log entries older than max_age_days in batches.

        Caller is responsible for committing the transaction.

        Args:
        ----
            db (AsyncSession): The database session.
            max_age_days (int): Retention period in days (default 90).
            batch_size (int): Maximum rows deleted per iteration
                (default 10 000).

        Returns:
        -------
            int: The total number of log entries deleted.

        """
        cutoff = utc_now_naive() - timedelta(days=max_age_days)
        total_deleted = 0

        while True:
            # Sub-select a batch of IDs to delete
            ids_subq = (
                select(APIKeyUsageLog.id)
                .where(APIKeyUsageLog.timestamp < cutoff)
                .limit(batch_size)
            ).scalar_subquery()

            stmt = delete(APIKeyUsageLog).where(APIKeyUsageLog.id.in_(ids_subq))
            result = cast(CursorResult[Any], await db.execute(stmt))
            total_deleted += result.rowcount
            if result.rowcount < batch_size:
                break

        return total_deleted

    async def get_keys_expiring_in_range(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
    ) -> list[APIKey]:
        """Get API keys expiring within a date range.

        Args:
        ----
            db (AsyncSession): The database session.
            start_date (datetime): Start of the date range (inclusive).
            end_date (datetime): End of the date range (exclusive).

        Returns:
        -------
            list[APIKey]: List of API keys expiring in the range.

        """
        query = select(self.model).where(
            and_(
                self.model.status == ApiKeyStatus.ACTIVE.value,
                self.model.expiration_date >= start_date,
                self.model.expiration_date < end_date,
            )
        )

        result = await db.execute(query)
        return list(result.scalars().all())


api_key = CRUDAPIKey(APIKey)
usage_buffer = UsageBuffer(
    flush_interval=settings.API_KEY_USAGE_FLUSH_INTERVAL_SECONDS,
    batch_size=settings.API_KEY_USAGE_FLUSH_BATCH_SIZE,
)
