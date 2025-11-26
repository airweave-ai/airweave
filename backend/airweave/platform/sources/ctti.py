"""CTTI source implementation.

This source connects to the AACT Clinical Trials PostgreSQL database, queries the nct_id column
from the studies table, and creates WebEntity instances with ClinicalTrials.gov URLs.
"""

import asyncio
import random
import time
from typing import Any, AsyncGenerator, Dict, Optional, Union

import asyncpg

from airweave.core.logging import logger
from airweave.platform.configs.auth import CTTIAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.ctti import CTTIWebEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage import storage_manager
from airweave.schemas.source_connection import AuthenticationMethod

# Global connection pool for CTTI to prevent connection exhaustion
_ctti_pool: Optional[asyncpg.Pool] = None
_ctti_pool_lock = asyncio.Lock()


async def get_ctti_pool(username: str, password: str) -> asyncpg.Pool:
    """Get or create the shared CTTI connection pool.

    Args:
        username: AACT database username
        password: AACT database password

    Returns:
        The shared connection pool
    """
    global _ctti_pool

    async with _ctti_pool_lock:
        if _ctti_pool is None:
            logger.info("Creating shared CTTI connection pool")
            _ctti_pool = await asyncpg.create_pool(
                host=CTTISource.AACT_HOST,
                port=CTTISource.AACT_PORT,
                user=username,
                password=password,
                database=CTTISource.AACT_DATABASE,
                min_size=2,  # Minimum connections in pool
                max_size=5,  # Reduced from 10 - AACT is a public DB with strict limits
                timeout=30.0,
                command_timeout=60.0,
            )
            logger.info("CTTI connection pool created successfully")

    return _ctti_pool


async def _retry_with_backoff(func, *args, max_retries=3, **kwargs):
    """Retry a function with exponential backoff.

    Args:
        func: The async function to retry
        *args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # Log the full error details
            error_type = type(e).__name__
            error_msg = str(e)

            # Don't retry on certain permanent errors
            if isinstance(
                e,
                (
                    asyncpg.InvalidPasswordError,
                    asyncpg.InvalidCatalogNameError,
                    ValueError,  # Our credential validation errors
                ),
            ):
                logger.error(f"Non-retryable database error: {error_type}: {error_msg}")
                raise e

            if attempt < max_retries:
                # Calculate delay with exponential backoff and jitter
                base_delay = 2**attempt  # 1s, 2s, 4s
                jitter = random.uniform(0.1, 0.5)  # Add randomness
                delay = base_delay + jitter

                logger.warning(
                    f"Database operation attempt {attempt + 1}/{max_retries + 1} failed with "
                    f"{error_type}: {error_msg}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries + 1} database operation attempts failed. "
                    f"Final error {error_type}: {error_msg}"
                )

    # Re-raise the last exception if all retries failed
    raise last_exception


@source(
    name="CTTI AACT",
    short_name="ctti",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="CTTIAuthConfig",
    config_class="CTTIConfig",
    labels=["Clinical Trials", "Database"],
    supports_continuous=False,
)
class CTTISource(BaseSource):
    """CTTI source connector integrates with the AACT PostgreSQL database to extract trials.

    Connects to the Aggregate Analysis of ClinicalTrials.gov database.

    It creates web entities that link to
    ClinicalTrials.gov pages.
    """

    # Hardcoded AACT database connection details
    AACT_HOST = "aact-db.ctti-clinicaltrials.org"
    AACT_PORT = 5432
    AACT_DATABASE = "aact"
    AACT_SCHEMA = "ctgov"
    AACT_TABLE = "studies"

    def __init__(self):
        """Initialize the CTTI source."""
        super().__init__()
        self.pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def create(
        cls,
        credentials: Union[Dict[str, Any], CTTIAuthConfig],
        config: Optional[Dict[str, Any]] = None,
    ) -> "CTTISource":
        """Create a new CTTI source instance.

        Args:
            credentials: CTTIAuthConfig object or dictionary containing AACT database credentials:
                - username: Username for AACT database
                - password: Password for AACT database
            config: Optional configuration parameters:
                - limit: Maximum number of studies to fetch (default: 10000)
                - skip: Number of studies to skip for pagination (default: 0)
        """
        instance = cls()
        instance.credentials = credentials  # Store credentials separately
        instance.config = config or {}  # Store config separately
        return instance

    def _get_credential(self, key: str) -> str:
        """Get a credential value from either dict or config object.

        Args:
            key: The credential key to retrieve

        Returns:
            The credential value

        Raises:
            ValueError: If the credential is missing or empty
        """
        # Try to get from object attribute first (CTTIAuthConfig)
        value = getattr(self.credentials, key, None)

        # If not found and credentials is a dict, try dict access
        if value is None and isinstance(self.credentials, dict):
            value = self.credentials.get(key)

        # Validate the value exists and is not empty
        if not value:
            raise ValueError(f"Missing or empty credential: {key}")

        return value

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Ensure connection pool is initialized and return it."""
        if not self.pool:
            username = self._get_credential("username")
            password = self._get_credential("password")

            # Use the shared connection pool
            self.pool = await get_ctti_pool(username, password)

        return self.pool

    async def _create_entity_worker(
        self,
        record: Any,
        *,
        limit: int,
        skip: int,
        total_records: int,
    ) -> Optional[CTTIWebEntity]:
        """Create a CTTI entity from a database record, skipping if already in storage."""
        nct_id = record["nct_id"]
        clean_nct_id = str(nct_id).strip()

        # Create entity_id using the nct_id
        entity_id = f"CTTI:study:{clean_nct_id}"

        # Check if entity already exists in Azure storage
        try:
            exists = await storage_manager.check_ctti_file_exists(self.logger, entity_id)
            if exists:
                self.logger.debug(f"Skipping entity {entity_id} - already exists in Azure storage")
                return None
        except Exception as e:
            # Log error but continue processing
            self.logger.warning(
                f"Error checking storage for {entity_id}: {e}. Continuing with entity creation."
            )

        # Create the ClinicalTrials.gov URL
        url = f"https://clinicaltrials.gov/study/{clean_nct_id}"

        # Create WebEntity
        return CTTIWebEntity(
            entity_id=entity_id,
            crawl_url=url,
            title=f"Clinical Trial {clean_nct_id}",
            description=(
                f"Clinical trial study from ClinicalTrials.gov with NCT ID: {clean_nct_id}"
            ),
            nct_id=clean_nct_id,
            study_url=url,
            data_source="ClinicalTrials.gov",
            breadcrumbs=[
                Breadcrumb(
                    entity_id="CTTI:source",
                    name="CTTI Clinical Trials",
                    entity_type="source",
                ),
                Breadcrumb(
                    entity_id=entity_id,
                    name=f"Clinical Trial {clean_nct_id}",
                    entity_type="clinical_trial",
                ),
            ],
            metadata={
                "source": "CTTI",
                "database_host": self.AACT_HOST,
                "database_name": self.AACT_DATABASE,
                "database_schema": self.AACT_SCHEMA,
                "database_table": self.AACT_TABLE,
                "original_nct_id": nct_id,
                "limit_used": limit,
                "skip_used": skip,
                "total_fetched": total_records,
            },
        )

    async def generate_entities(self) -> AsyncGenerator[Union[CTTIWebEntity], None]:
        """Generate WebEntity instances for each nct_id in the AACT studies table.

        Skips entities that already exist in Azure storage to avoid redundant processing.
        """
        try:
            # Get the connection pool
            pool = await self._ensure_pool()

            # Get the limit and skip from config
            limit = self.config.get("limit", 10000)
            skip = self.config.get("skip", 0)

            # Simple query - URL construction in Python is fine
            query = f"""
                SELECT nct_id
                FROM "{CTTISource.AACT_SCHEMA}"."{CTTISource.AACT_TABLE}"
                WHERE nct_id IS NOT NULL
                ORDER BY nct_id
                LIMIT {limit}
                OFFSET {skip}
            """

            async def _execute_query():
                # Use connection from pool
                async with pool.acquire() as conn:
                    if skip > 0:
                        self.logger.info(
                            f"Executing query to fetch {limit} clinical trials from AACT database "
                            f"(skipping first {skip} records)"
                        )
                    else:
                        self.logger.info(
                            f"Executing query to fetch {limit} clinical trials from AACT database"
                        )
                    records = await conn.fetch(query)
                    self.logger.info(f"Successfully fetched {len(records)} clinical trial records")
                    return records

            # Use retry logic for query execution
            records = await _retry_with_backoff(_execute_query)

            self.logger.info(f"Starting to process {len(records)} records into CTTI entities")

            # Filter out invalid records upfront
            valid_records = []
            for record in records:
                nct_id = record["nct_id"]
                if nct_id and str(nct_id).strip():
                    valid_records.append(record)

            if not valid_records:
                self.logger.warning("No valid records found after filtering")
                return

            start_time = time.time()

            self.logger.info(
                f"Processing {len(valid_records)} valid records in batches "
                f"(checking Azure storage for existing entities)"
            )

            # Process records in batches using concurrent processing
            # batch_size=50 provides good throughput for Azure storage I/O operations
            # The concurrent batching significantly speeds up storage existence checks
            entities_created = 0
            batch_size = 50

            async for entity in self.process_entities_concurrent(
                items=valid_records,
                worker=lambda rec: self._create_entity_worker(
                    rec, limit=limit, skip=skip, total_records=len(valid_records)
                ),
                batch_size=batch_size,
                preserve_order=False,  # Order doesn't matter for CTTI entities
                stop_on_error=False,  # Continue processing even if one entity fails
                max_queue_size=200,  # Reasonable queue size for batching
            ):
                entities_created += 1

                # Log progress every 100 entities
                if entities_created % 100 == 0:
                    self.logger.info(f"Created {entities_created} new CTTI entities")
                    await asyncio.sleep(0)  # Allow other tasks to run

                yield entity

            end_time = time.time()
            duration = end_time - start_time

            # Calculate skipped count (entities that were filtered out by worker)
            self.logger.info(
                f"Completed processing: {entities_created} new CTTI entities created, "
                f"~{len(valid_records) - entities_created} skipped (already in storage), "
                f"Time taken: {duration:.4f} seconds"
            )

        except Exception as e:
            self.logger.error(f"Error in CTTI source generate_entities: {str(e)}")
            raise
        # Note: We don't close the pool here as it's shared across all CTTI instances

    async def validate(self) -> bool:
        """Verify CTTI DB credentials and basic access by running a tiny query."""
        try:
            # Ensure pool is initialized (also validates username/password)
            pool = await self._ensure_pool()

            # Lightweight permission/reachability check against the exact table we read later.
            async def _ping():
                async with pool.acquire() as conn:
                    # Touch the studies table; result may be None if table is
                    # empty—success still means access is OK.
                    await conn.fetchval(
                        f'SELECT 1 FROM "{self.AACT_SCHEMA}"."{self.AACT_TABLE}" LIMIT 1'
                    )

            # A couple of retries in case of transient network hiccups
            await _retry_with_backoff(_ping, max_retries=2)
            return True

        except (asyncpg.InvalidPasswordError, asyncpg.InvalidCatalogNameError, ValueError) as e:
            # Non-retryable credential/config errors
            self.logger.error(f"CTTI validation failed (credentials/config): {e}")
            return False
        except Exception as e:
            self.logger.error(f"CTTI validation encountered an error: {e}")
            return False
