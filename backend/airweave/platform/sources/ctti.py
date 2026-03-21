"""CTTI source implementation.

This source connects to the AACT Clinical Trials PostgreSQL database, queries the nct_id column
from the studies table, and creates WebEntity instances with ClinicalTrials.gov URLs.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import AsyncGenerator

import asyncpg

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import CTTIAuthConfig
from airweave.platform.configs.config import CTTIConfig
from airweave.platform.cursors import CTTICursor
from airweave.platform.decorators import source
from airweave.platform.entities.ctti import CTTIWebEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="CTTI AACT",
    short_name="ctti",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=CTTIAuthConfig,
    config_class=CTTIConfig,
    labels=["Clinical Trials", "Database"],
    supports_continuous=True,
    cursor_class=CTTICursor,
)
class CTTISource(BaseSource):
    """CTTI source connector integrates with the AACT PostgreSQL database to extract trials.

    Connects to the Aggregate Analysis of ClinicalTrials.gov database.
    Creates web entities that link to ClinicalTrials.gov pages.
    """

    # Hardcoded AACT database connection details
    AACT_HOST = "aact-db.ctti-clinicaltrials.org"
    AACT_PORT = 5432
    AACT_DATABASE = "aact"
    AACT_SCHEMA = "ctgov"
    AACT_TABLE = "studies"

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize with an empty connection pool."""
        super().__init__(auth=auth, logger=logger, http_client=http_client)
        self.pool: asyncpg.Pool | None = None

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: CTTIConfig,
    ) -> CTTISource:
        """Create a new CTTI source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._limit = config.limit
        return instance

    async def _retry_with_backoff(self, func, *args, max_retries: int = 3, **kwargs):
        """Retry a function with exponential backoff."""
        last_exception = None

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                error_msg = str(e)

                # Don't retry on certain permanent errors
                if isinstance(
                    e,
                    (
                        asyncpg.InvalidPasswordError,
                        asyncpg.InvalidCatalogNameError,
                        ValueError,
                    ),
                ):
                    self.logger.warning(f"Non-retryable database error: {error_type}: {error_msg}")
                    raise e

                if attempt < max_retries:
                    base_delay = 2**attempt  # 1s, 2s, 4s
                    jitter = 0.1 + secrets.randbelow(401) / 1000
                    delay = base_delay + jitter

                    self.logger.warning(
                        f"Database operation attempt {attempt + 1}/{max_retries + 1} failed with "
                        f"{error_type}: {error_msg}. Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.warning(
                        f"All {max_retries + 1} database operation attempts failed. "
                        f"Final error {error_type}: {error_msg}"
                    )

        raise last_exception

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Ensure connection pool is initialized and return it."""
        if not self.pool:
            creds: CTTIAuthConfig = self.auth.credentials
            username = creds.username
            password = creds.password

            self.logger.debug("Creating CTTI connection pool")
            self.pool = await asyncpg.create_pool(
                host=self.AACT_HOST,
                port=self.AACT_PORT,
                user=username,
                password=password,
                database=self.AACT_DATABASE,
                min_size=1,
                max_size=3,  # Conservative limit for public DB
                timeout=30.0,
                command_timeout=60.0,
            )
            self.logger.debug("CTTI connection pool created successfully")

        return self.pool

    async def _close_pool(self) -> None:
        """Close the connection pool if it exists."""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _fetch_records(self, last_nct_id: str, remaining: int, total_synced: int, limit: int):
        """Fetch clinical trial records from the AACT database."""
        if last_nct_id:
            self.logger.debug(
                f"📊 Incremental sync from NCT_ID > {last_nct_id} "
                f"({total_synced}/{limit} synced, {remaining} remaining)"
            )
        else:
            self.logger.debug(f"🔄 Full sync (no cursor), limit={limit}")

        pool = await self._ensure_pool()

        if last_nct_id:
            query = f"""
                SELECT nct_id
                FROM "{self.AACT_SCHEMA}"."{self.AACT_TABLE}"
                WHERE nct_id IS NOT NULL AND nct_id > $1
                ORDER BY nct_id ASC
                LIMIT {remaining}
            """
            query_args = [last_nct_id]
        else:
            query = f"""
                SELECT nct_id
                FROM "{self.AACT_SCHEMA}"."{self.AACT_TABLE}"
                WHERE nct_id IS NOT NULL
                ORDER BY nct_id ASC
                LIMIT {remaining}
            """
            query_args = []

        async def _execute_query():
            async with pool.acquire() as conn:
                if last_nct_id:
                    self.logger.debug(
                        f"Fetching up to {remaining} clinical trials from AACT "
                        f"(NCT_ID > {last_nct_id})"
                    )
                else:
                    self.logger.debug(
                        f"Fetching up to {remaining} clinical trials from AACT (full sync)"
                    )
                records = await conn.fetch(query, *query_args)
                self.logger.debug(f"Fetched {len(records)} clinical trial records")
                return records

        return await self._retry_with_backoff(_execute_query)

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[CTTIWebEntity, None]:
        """Generate WebEntity instances for each nct_id in the AACT studies table."""
        try:
            cursor_data = cursor.data if cursor else {}
            last_nct_id = cursor_data.get("last_nct_id", "")
            total_synced = cursor_data.get("total_synced", 0)

            limit = self._limit

            remaining = limit - total_synced

            if remaining <= 0:
                self.logger.info(
                    f"✅ Limit reached: {total_synced}/{limit} records already synced. "
                    f"Skipping sync. To sync more, increase the limit configuration."
                )
                return

            records = await self._fetch_records(last_nct_id, remaining, total_synced, limit)

            self.logger.debug(f"Processing {len(records)} records into entities")
            entities_created = 0

            for record in records:
                row = dict(record)
                entity = CTTIWebEntity.from_api(row)
                if entity is None:
                    continue

                entities_created += 1

                if entities_created % 100 == 0:
                    self.logger.debug(f"Created {entities_created}/{len(records)} CTTI entities")

                if entities_created % 10 == 0:
                    await asyncio.sleep(0)

                yield entity

                if cursor:
                    cursor.update(
                        last_nct_id=entity.nct_id,
                        total_synced=total_synced + entities_created,
                    )

            self.logger.debug(
                f"Completed creating {entities_created} CTTI entities "
                f"(total synced: {total_synced + entities_created}/{limit})"
            )

        except Exception as e:
            self.logger.warning(f"Error in CTTI generate_entities: {e}")
            raise
        finally:
            await self._close_pool()

    async def validate(self) -> None:
        """Verify CTTI DB credentials and basic access by running a tiny query."""
        try:
            pool = await self._ensure_pool()

            async def _ping():
                async with pool.acquire() as conn:
                    await conn.fetchval(
                        f'SELECT 1 FROM "{self.AACT_SCHEMA}"."{self.AACT_TABLE}" LIMIT 1'
                    )

            await self._retry_with_backoff(_ping, max_retries=2)

        except (asyncpg.InvalidPasswordError, asyncpg.InvalidCatalogNameError, ValueError) as e:
            self.logger.warning(f"CTTI validation failed (credentials/config): {e}")
            raise
        except Exception as e:
            self.logger.warning(f"CTTI validation encountered an error: {e}")
            raise
        finally:
            await self._close_pool()
