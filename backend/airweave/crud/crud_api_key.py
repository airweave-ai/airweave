"""CRUD operations for the APIKey model."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core import credentials
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

_background_tasks: set[asyncio.Task] = set()


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
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        expiration_days = obj_in.expiration_days if obj_in.expiration_days is not None else 90
        expiration_date = utc_now_naive() + timedelta(days=expiration_days)

        api_key_data = {
            "encrypted_key": encrypted_key,
            "expiration_date": expiration_date,
            "status": ApiKeyStatus.ACTIVE.value,
            "key_prefix": key[:8],
            "key_hash": key_hash,
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
        """Look up an API key by its SHA-256 hash (O(1) indexed lookup).

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
        key_hash = hashlib.sha256(key.encode()).hexdigest()
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

        if api_key.status == ApiKeyStatus.EXPIRED.value:
            raise PermissionException("API key has expired")

        if api_key.expiration_date < now:
            raise PermissionException("API key has expired")

        if api_key.status == ApiKeyStatus.REVOKED.value:
            raise PermissionException("API key has been revoked")

        return api_key

    async def revoke(
        self,
        db: AsyncSession,
        *,
        api_key_id: UUID,
    ) -> APIKey:
        """Revoke an active key immediately.

        Uses a WHERE ``status='active'`` guard to prevent concurrent
        revocation races.

        Args:
        ----
            db (AsyncSession): The database session.
            api_key_id (UUID): The ID of the key to revoke.

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
        result = await db.execute(stmt)

        if result.rowcount == 0:
            raise ConflictException("API key is not active (already revoked or expired)")

        await db.flush()

        refreshed = await db.get(self.model, api_key_id)
        if refreshed is None:
            raise NotFoundException(
                f"API key {api_key_id} not found after revocation"
            )
        return refreshed

    async def record_usage(
        self,
        db: AsyncSession,
        *,
        api_key_obj: APIKey,
        ip_address: str,
        endpoint: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Update last_used_date/ip inline; fire-and-forget usage log INSERT.

        The usage log INSERT runs as a background task in a separate DB
        session to avoid adding write latency to the auth hot path. If
        it fails, the inline UPDATE on the key itself still succeeds.

        Args:
        ----
            db (AsyncSession): The database session (for the inline
                UPDATE).
            api_key_obj (APIKey): The API key being used.
            ip_address (str): The client IP address.
            endpoint (str): The endpoint path being accessed.
            user_agent (Optional[str]): The client User-Agent header.

        """
        now = utc_now_naive()

        stmt = (
            update(self.model)
            .where(self.model.id == api_key_obj.id)
            .values(last_used_date=now, last_used_ip=ip_address)
        )
        await db.execute(stmt)

        async def _insert_log() -> None:
            try:
                async with get_db_context() as log_db:
                    log_entry = APIKeyUsageLog(
                        api_key_id=api_key_obj.id,
                        organization_id=api_key_obj.organization_id,
                        timestamp=now,
                        ip_address=ip_address,
                        endpoint=endpoint,
                        user_agent=user_agent,
                    )
                    log_db.add(log_entry)
                    await log_db.commit()
            except Exception as e:
                logger.warning("Failed to insert usage log entry: %s", e)

        task = asyncio.create_task(_insert_log())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

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
        result = await db.execute(stmt)
        return result.rowcount

    async def prune_usage_log(self, db: AsyncSession, *, max_age_days: int = 90) -> int:
        """Delete usage log entries older than max_age_days.

        Caller is responsible for committing the transaction.

        Args:
        ----
            db (AsyncSession): The database session.
            max_age_days (int): Retention period in days (default 90).

        Returns:
        -------
            int: The number of log entries deleted.

        """
        cutoff = utc_now_naive() - timedelta(days=max_age_days)
        stmt = delete(APIKeyUsageLog).where(APIKeyUsageLog.timestamp < cutoff)
        result = await db.execute(stmt)
        return result.rowcount

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
                self.model.expiration_date >= start_date,
                self.model.expiration_date < end_date,
            )
        )

        result = await db.execute(query)
        return list(result.scalars().all())


api_key = CRUDAPIKey(APIKey)
