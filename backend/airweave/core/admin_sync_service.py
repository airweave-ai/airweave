"""Admin sync service for efficient sync listing and counting operations.

This module handles the complex logic for admin sync listing, including:
- Query building with multiple filters
- Bulk data fetching for entity counts, job info, tags
- Optimized destination counting with connection pooling
- ARF entity counting
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.deps import ApiContext
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.models.collection import Collection
from airweave.models.connection import Connection
from airweave.models.entity_count import EntityCount
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.models.sync_connection import SyncConnection
from airweave.models.sync_job import SyncJob


class AdminSyncQueryBuilder:
    """Builds complex SQL queries for admin sync listing with multiple filters."""

    def __init__(self):
        """Initialize query builder."""
        self.query = select(Sync)

    def with_sync_ids(self, sync_ids: List[UUID]) -> "AdminSyncQueryBuilder":
        """Filter by specific sync IDs."""
        if sync_ids:
            self.query = self.query.where(Sync.id.in_(sync_ids))
        return self

    def with_organization_id(self, organization_id: UUID) -> "AdminSyncQueryBuilder":
        """Filter by organization ID."""
        if organization_id:
            self.query = self.query.where(Sync.organization_id == organization_id)
        return self

    def with_status(self, status: str) -> "AdminSyncQueryBuilder":
        """Filter by sync status."""
        if status is not None:
            try:
                status_enum = SyncStatus(status.lower())
                self.query = self.query.where(Sync.status == status_enum)
            except ValueError:
                # Invalid status - query will return nothing
                self.query = self.query.where(Sync.id == None)  # noqa: E711
        return self

    def with_source_connection_filter(self, has_source_connection: bool) -> "AdminSyncQueryBuilder":
        """Filter by presence of source connection."""
        if has_source_connection:
            # Only syncs with source connection
            self.query = self.query.where(
                Sync.id.in_(
                    select(SourceConnection.sync_id).where(SourceConnection.sync_id.isnot(None))
                )
            )
        else:
            # Only orphaned syncs
            self.query = self.query.where(
                Sync.id.notin_(
                    select(SourceConnection.sync_id).where(SourceConnection.sync_id.isnot(None))
                )
            )
        return self

    def with_is_authenticated(self, is_authenticated: bool) -> "AdminSyncQueryBuilder":
        """Filter by authentication status."""
        if is_authenticated is not None:
            self.query = self.query.where(
                Sync.id.in_(
                    select(SourceConnection.sync_id).where(
                        SourceConnection.is_authenticated == is_authenticated
                    )
                )
            )
        return self

    def with_collection_id(self, collection_id: str) -> "AdminSyncQueryBuilder":
        """Filter by readable collection ID."""
        if collection_id is not None:
            self.query = self.query.where(
                Sync.id.in_(
                    select(SourceConnection.sync_id).where(
                        SourceConnection.readable_collection_id == collection_id
                    )
                )
            )
        return self

    def with_source_type(self, source_type: str) -> "AdminSyncQueryBuilder":
        """Filter by source short name."""
        if source_type is not None:
            self.query = self.query.where(
                Sync.id.in_(
                    select(SourceConnection.sync_id).where(
                        SourceConnection.short_name == source_type
                    )
                )
            )
        return self

    def with_last_job_status(self, last_job_status: str) -> "AdminSyncQueryBuilder":
        """Filter by most recent job status."""
        if last_job_status is not None:
            try:
                status_enum = SyncJobStatus(last_job_status.lower())

                # Subquery for most recent job per sync
                latest_job_subq = select(
                    SyncJob.sync_id,
                    SyncJob.status,
                    func.row_number()
                    .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                    .label("rn"),
                ).subquery()

                self.query = self.query.where(
                    Sync.id.in_(
                        select(latest_job_subq.c.sync_id).where(
                            latest_job_subq.c.rn == 1,
                            latest_job_subq.c.status == status_enum,
                        )
                    )
                )
            except ValueError:
                # Invalid status
                self.query = self.query.where(Sync.id == None)  # noqa: E711
        return self

    def with_ghost_syncs_filter(self, last_n: int) -> "AdminSyncQueryBuilder":
        """Filter to syncs where last N jobs all failed."""
        if last_n is not None and last_n > 0:
            # Subquery for last N completed jobs per sync
            jobs_subq = (
                select(
                    SyncJob.sync_id,
                    SyncJob.status,
                    func.row_number()
                    .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                    .label("rn"),
                )
                .where(
                    SyncJob.status.notin_(
                        [SyncJobStatus.RUNNING.value, SyncJobStatus.PENDING.value]
                    )
                )
                .subquery()
            )

            # Syncs where all last N jobs failed
            failed_syncs_subq = (
                select(jobs_subq.c.sync_id)
                .where(jobs_subq.c.rn <= last_n)
                .group_by(jobs_subq.c.sync_id)
                .having(
                    func.count().filter(jobs_subq.c.status == SyncJobStatus.FAILED.value)
                    == func.count()
                )
                .having(func.count() >= last_n)
                .subquery()
            )

            self.query = self.query.where(Sync.id.in_(select(failed_syncs_subq.c.sync_id)))
        return self

    def with_tags_filter(self, tags: str) -> "AdminSyncQueryBuilder":
        """Filter to syncs with jobs having ANY of the specified tags."""
        if tags is not None:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                tagged_jobs_subq = (
                    select(SyncJob.sync_id)
                    .where(
                        SyncJob.sync_id.in_(select(Sync.id)),
                        SyncJob.sync_metadata.isnot(None),
                        SyncJob.sync_metadata["tags"].op("?|")(array(tag_list)),
                    )
                    .distinct()
                )
                self.query = self.query.where(Sync.id.in_(tagged_jobs_subq))
        return self

    def with_exclude_tags_filter(self, exclude_tags: str) -> "AdminSyncQueryBuilder":
        """Exclude syncs with jobs having ANY of the specified tags."""
        if exclude_tags is not None:
            exclude_tag_list = [t.strip() for t in exclude_tags.split(",") if t.strip()]
            if exclude_tag_list:
                excluded_jobs_subq = (
                    select(SyncJob.sync_id)
                    .where(
                        SyncJob.sync_id.in_(select(Sync.id)),
                        SyncJob.sync_metadata.isnot(None),
                        SyncJob.sync_metadata["tags"].op("?|")(array(exclude_tag_list)),
                    )
                    .distinct()
                )
                self.query = self.query.where(Sync.id.notin_(excluded_jobs_subq))
        return self

    def with_pagination(self, skip: int, limit: int) -> "AdminSyncQueryBuilder":
        """Add pagination."""
        self.query = self.query.order_by(Sync.created_at.desc()).offset(skip).limit(limit)
        return self

    def build(self):
        """Return the final query."""
        return self.query


class AdminSyncService:
    """Service for admin sync operations with optimized bulk fetching."""

    MAX_CONCURRENT_DESTINATION_QUERIES = 10  # Reduced from 20 to prevent overload

    async def list_syncs_with_metadata(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        sync_ids: Optional[List[UUID]] = None,
        organization_id: Optional[UUID] = None,
        collection_id: Optional[str] = None,
        source_type: Optional[str] = None,
        has_source_connection: bool = True,
        is_authenticated: Optional[bool] = None,
        status: Optional[str] = None,
        last_job_status: Optional[str] = None,
        ghost_syncs_last_n: Optional[int] = None,
        tags: Optional[str] = None,
        exclude_tags: Optional[str] = None,
        include_destination_counts: bool = False,
        include_arf_counts: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """List syncs with extensive metadata and timing information.

        Args:
            db: Database session
            ctx: API context with logger
            skip: Pagination offset
            limit: Max results
            sync_ids: Filter by specific sync IDs
            organization_id: Filter by organization
            collection_id: Filter by collection readable ID
            source_type: Filter by source short name
            has_source_connection: Include syncs with/without source connection
            is_authenticated: Filter by auth status
            status: Filter by sync status
            last_job_status: Filter by last job status
            ghost_syncs_last_n: Filter to syncs with N consecutive failures
            tags: Filter by job tags (comma-separated)
            exclude_tags: Exclude syncs with these tags
            include_destination_counts: Query Qdrant/Vespa (slow)
            include_arf_counts: Query ARF storage (slow)

        Returns:
            Tuple of (sync_data_list, timings_dict)
        """
        request_start = time.monotonic()
        timings = {}

        # Build and execute main query
        query_start = time.monotonic()
        query = (
            AdminSyncQueryBuilder()
            .with_sync_ids(sync_ids)
            .with_organization_id(organization_id)
            .with_status(status)
            .with_source_connection_filter(has_source_connection)
            .with_is_authenticated(is_authenticated)
            .with_collection_id(collection_id)
            .with_source_type(source_type)
            .with_last_job_status(last_job_status)
            .with_ghost_syncs_filter(ghost_syncs_last_n)
            .with_tags_filter(tags)
            .with_exclude_tags_filter(exclude_tags)
            .with_pagination(skip, limit)
            .build()
        )

        result = await db.execute(query)
        syncs = list(result.scalars().all())
        timings["main_query"] = (time.monotonic() - query_start) * 1000

        if not syncs:
            timings["total"] = (time.monotonic() - request_start) * 1000
            return [], timings

        sync_ids_list = [s.id for s in syncs]

        # Phase 1: Fetch metadata that doesn't depend on source_conn_map
        (
            entity_count_map,
            arf_count_map,
            last_job_map,
            all_tags_map,
            source_conn_map,
            sync_connections,
        ) = await asyncio.gather(
            self._fetch_entity_counts(db, sync_ids_list, timings),
            self._fetch_arf_counts(syncs, include_arf_counts, ctx, timings),
            self._fetch_last_job_info(db, sync_ids_list, timings),
            self._fetch_all_tags(db, sync_ids_list, timings),
            self._fetch_source_connections(db, sync_ids_list, timings),
            self._fetch_sync_connections(db, sync_ids_list, timings),
        )

        # Phase 2: Fetch destination counts that depend on source_conn_map
        if include_destination_counts:
            qdrant_count_map, vespa_count_map = await asyncio.gather(
                self._fetch_destination_counts(
                    syncs, source_conn_map, include_destination_counts, ctx, timings, is_qdrant=True
                ),
                self._fetch_destination_counts(
                    syncs,
                    source_conn_map,
                    include_destination_counts,
                    ctx,
                    timings,
                    is_qdrant=False,
                ),
            )
        else:
            qdrant_count_map = {s.id: None for s in syncs}
            vespa_count_map = {s.id: None for s in syncs}
            timings["destination_counts_qdrant"] = 0
            timings["destination_counts_vespa"] = 0

        # Build response data
        build_start = time.monotonic()
        sync_data_list = self._build_sync_data_list(
            syncs=syncs,
            sync_connections=sync_connections,
            source_conn_map=source_conn_map,
            last_job_map=last_job_map,
            all_tags_map=all_tags_map,
            entity_count_map=entity_count_map,
            arf_count_map=arf_count_map,
            qdrant_count_map=qdrant_count_map,
            vespa_count_map=vespa_count_map,
        )
        timings["build_response"] = (time.monotonic() - build_start) * 1000
        timings["total"] = (time.monotonic() - request_start) * 1000

        return sync_data_list, timings

    async def _fetch_entity_counts(
        self, db: AsyncSession, sync_ids: List[UUID], timings: Dict[str, float]
    ) -> Dict[UUID, int]:
        """Fetch entity counts from Postgres."""
        start = time.monotonic()
        query = (
            select(EntityCount.sync_id, func.sum(EntityCount.count).label("total_count"))
            .where(EntityCount.sync_id.in_(sync_ids))
            .group_by(EntityCount.sync_id)
        )
        result = await db.execute(query)
        entity_count_map = {row.sync_id: row.total_count or 0 for row in result}
        timings["entity_counts"] = (time.monotonic() - start) * 1000
        return entity_count_map

    async def _fetch_arf_counts(
        self,
        syncs: List[Sync],
        include_arf_counts: bool,
        ctx: ApiContext,
        timings: Dict[str, float],
    ) -> Dict[UUID, Optional[int]]:
        """Fetch ARF entity counts if requested."""
        if not include_arf_counts:
            timings["arf_counts"] = 0
            return {s.id: None for s in syncs}

        start = time.monotonic()
        from airweave.platform.sync.arf.service import ArfService

        arf_service = ArfService()

        async def get_arf_count_safe(sync_id: UUID) -> Optional[int]:
            try:
                return await arf_service.get_entity_count(str(sync_id))
            except Exception as e:
                ctx.logger.warning(f"Failed to fetch ARF count for sync {sync_id}: {e}")
                return None

        # Limit concurrency to prevent overload
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DESTINATION_QUERIES)

        async def get_with_limit(sync_id: UUID) -> Tuple[UUID, Optional[int]]:
            async with semaphore:
                count = await get_arf_count_safe(sync_id)
                return sync_id, count

        results = await asyncio.gather(*[get_with_limit(s.id) for s in syncs])
        arf_count_map = dict(results)
        timings["arf_counts"] = (time.monotonic() - start) * 1000
        return arf_count_map

    async def _fetch_last_job_info(
        self, db: AsyncSession, sync_ids: List[UUID], timings: Dict[str, float]
    ) -> Dict[UUID, Dict[str, Any]]:
        """Fetch last job information for each sync."""
        start = time.monotonic()
        last_job_subq = (
            select(
                SyncJob.sync_id,
                SyncJob.status,
                SyncJob.completed_at,
                SyncJob.error,
                SyncJob.sync_metadata,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(SyncJob.sync_id.in_(sync_ids))
            .subquery()
        )
        query = select(last_job_subq).where(last_job_subq.c.rn == 1)
        result = await db.execute(query)
        last_job_map = {
            row.sync_id: {
                "status": row.status,
                "completed_at": row.completed_at,
                "error": row.error,
                "sync_metadata": row.sync_metadata,
            }
            for row in result
        }
        timings["last_job_info"] = (time.monotonic() - start) * 1000
        return last_job_map

    async def _fetch_all_tags(
        self, db: AsyncSession, sync_ids: List[UUID], timings: Dict[str, float]
    ) -> Dict[UUID, List[str]]:
        """Fetch all unique tags from all jobs for each sync."""
        start = time.monotonic()
        query = select(SyncJob.sync_id, SyncJob.sync_metadata).where(
            SyncJob.sync_id.in_(sync_ids),
            SyncJob.sync_metadata.isnot(None),
        )
        result = await db.execute(query)

        # Aggregate unique tags per sync
        all_tags_map = {}
        for row in result:
            if row.sync_metadata and isinstance(row.sync_metadata, dict):
                tags = row.sync_metadata.get("tags")
                if tags and isinstance(tags, list):
                    if row.sync_id not in all_tags_map:
                        all_tags_map[row.sync_id] = set()
                    all_tags_map[row.sync_id].update(tags)

        # Convert to sorted lists
        all_tags_map = {sync_id: sorted(list(tag_set)) for sync_id, tag_set in all_tags_map.items()}
        timings["all_tags"] = (time.monotonic() - start) * 1000
        return all_tags_map

    async def _fetch_source_connections(
        self, db: AsyncSession, sync_ids: List[UUID], timings: Dict[str, float]
    ) -> Dict[UUID, Dict[str, Any]]:
        """Fetch source connection info with collection IDs."""
        start = time.monotonic()
        query = (
            select(
                SourceConnection.sync_id,
                SourceConnection.short_name,
                SourceConnection.readable_collection_id,
                SourceConnection.is_authenticated,
                Collection.id.label("collection_id"),
            )
            .outerjoin(
                Collection, SourceConnection.readable_collection_id == Collection.readable_id
            )
            .where(SourceConnection.sync_id.in_(sync_ids))
        )
        result = await db.execute(query)
        source_conn_map = {
            row.sync_id: {
                "short_name": row.short_name,
                "readable_collection_id": row.readable_collection_id,
                "is_authenticated": row.is_authenticated,
                "collection_id": row.collection_id,
            }
            for row in result
        }
        timings["source_connections"] = (time.monotonic() - start) * 1000
        # Need to wait for this to complete before destination counts
        return source_conn_map

    async def _fetch_sync_connections(
        self, db: AsyncSession, sync_ids: List[UUID], timings: Dict[str, float]
    ) -> Dict[UUID, Dict[str, Any]]:
        """Fetch sync connections to enrich with connection IDs."""
        start = time.monotonic()
        query = (
            select(SyncConnection, Connection)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(SyncConnection.sync_id.in_(sync_ids))
        )
        result = await db.execute(query)

        sync_connections = {}
        for sync_conn, connection in result:
            sync_id = sync_conn.sync_id
            if sync_id not in sync_connections:
                sync_connections[sync_id] = {"source": None, "destinations": []}
            if connection.integration_type.value == "source":
                sync_connections[sync_id]["source"] = connection.id
            elif connection.integration_type.value == "destination":
                sync_connections[sync_id]["destinations"].append(connection.id)

        timings["sync_connections"] = (time.monotonic() - start) * 1000
        return sync_connections

    async def _return_none_map(
        self, syncs: List[Sync], timing_key: str, timings: Dict[str, float]
    ) -> Dict[UUID, None]:
        """Return a map of None values when counts are not requested."""
        timings[timing_key] = 0
        return {s.id: None for s in syncs}

    async def _fetch_destination_counts(
        self,
        syncs: List[Sync],
        source_conn_map: Dict[UUID, Dict[str, Any]],
        include_counts: bool,
        ctx: ApiContext,
        timings: Dict[str, float],
        is_qdrant: bool = True,
    ) -> Dict[UUID, Optional[int]]:
        """Fetch document counts from either Qdrant or Vespa.

        Optimized to reuse destination instances per collection and limit concurrency.
        """
        timing_key = "destination_counts_qdrant" if is_qdrant else "destination_counts_vespa"

        if not include_counts:
            timings[timing_key] = 0
            return {s.id: None for s in syncs}

        start = time.monotonic()
        count_map = {}

        # Group syncs by collection for connection reuse
        syncs_by_collection: Dict[UUID, List[Sync]] = {}
        for sync in syncs:
            source_info = source_conn_map.get(sync.id, {})
            coll_id = source_info.get("collection_id")
            if not coll_id:
                count_map[sync.id] = None
                continue
            if coll_id not in syncs_by_collection:
                syncs_by_collection[coll_id] = []
            syncs_by_collection[coll_id].append(sync)

        # Process each collection (reuse connection per collection)
        async def process_collection(collection_id: UUID, collection_syncs: List[Sync]):
            try:
                if is_qdrant:
                    return await self._count_qdrant_for_collection(
                        collection_id, collection_syncs, ctx
                    )
                else:
                    return await self._count_vespa_for_collection(
                        collection_id, collection_syncs, ctx
                    )
            except Exception as e:
                ctx.logger.error(
                    f"Failed to count {'Qdrant' if is_qdrant else 'Vespa'} "
                    f"for collection {collection_id}: {e}"
                )
                return {sync.id: None for sync in collection_syncs}

        # Process all collections in parallel
        results = await asyncio.gather(
            *[
                process_collection(coll_id, coll_syncs)
                for coll_id, coll_syncs in syncs_by_collection.items()
            ],
            return_exceptions=True,
        )

        # Merge results
        for result in results:
            if isinstance(result, Exception):
                ctx.logger.error(f"Collection processing failed: {result}")
                continue
            count_map.update(result)

        timings[timing_key] = (time.monotonic() - start) * 1000
        return count_map

    async def _count_qdrant_for_collection(
        self, collection_id: UUID, syncs: List[Sync], ctx: ApiContext
    ) -> Dict[UUID, Optional[int]]:
        """Count Qdrant documents for all syncs in a collection (reuse client)."""
        from airweave.platform.destinations.qdrant import QdrantDestination

        try:
            # Create destination once for the collection
            qdrant = await QdrantDestination.create(
                collection_id=collection_id,
                organization_id=syncs[0].organization_id,
                logger=ctx.logger,
            )

            # Count with limited concurrency
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DESTINATION_QUERIES)

            async def count_sync(sync: Sync) -> Tuple[UUID, Optional[int]]:
                async with semaphore:
                    try:
                        scroll_filter = {
                            "must": [
                                {
                                    "key": "airweave_system_metadata.sync_id",
                                    "match": {"value": str(sync.id)},
                                }
                            ]
                        }
                        # Use exact=False for faster approximate counts
                        count_result = await qdrant.client.count(
                            collection_name=qdrant.collection_name,
                            count_filter=scroll_filter,
                            exact=False,  # Much faster, slight inaccuracy acceptable
                        )
                        return sync.id, count_result.count
                    except Exception as e:
                        ctx.logger.warning(f"Failed to count Qdrant for sync {sync.id}: {e}")
                        return sync.id, None

            results = await asyncio.gather(*[count_sync(s) for s in syncs])
            return dict(results)

        except Exception as e:
            ctx.logger.error(f"Failed to create Qdrant destination: {e}")
            return {s.id: None for s in syncs}

    async def _count_vespa_for_collection(
        self, collection_id: UUID, syncs: List[Sync], ctx: ApiContext
    ) -> Dict[UUID, Optional[int]]:
        """Count Vespa documents for all syncs in a collection (reuse client)."""
        from airweave.platform.destinations.vespa import VespaDestination

        try:
            # Create destination once for the collection
            vespa = await VespaDestination.create(
                collection_id=collection_id,
                organization_id=syncs[0].organization_id,
                logger=ctx.logger,
            )

            # Count with limited concurrency
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DESTINATION_QUERIES)

            async def count_sync(sync: Sync) -> Tuple[UUID, Optional[int]]:
                async with semaphore:
                    try:
                        # Query all Vespa schemas (base, file, code_file, email, web)
                        schemas = (
                            "base_entity, file_entity, code_file_entity, email_entity, web_entity"
                        )
                        yql = (
                            f"select * from sources {schemas} "
                            f"where airweave_system_metadata_sync_id contains '{sync.id}' "
                            f"and airweave_system_metadata_collection_id contains '{collection_id}' "
                            f"limit 0"
                        )

                        query_params = {"yql": yql}
                        # Use the refactored VespaClient for queries
                        response = await vespa._client.execute_query(query_params)
                        return sync.id, response.total_count
                    except Exception as e:
                        ctx.logger.warning(f"Failed to count Vespa for sync {sync.id}: {e}")
                        return sync.id, None

            results = await asyncio.gather(*[count_sync(s) for s in syncs])
            return dict(results)

        except Exception as e:
            ctx.logger.error(f"Failed to create Vespa destination: {e}")
            return {s.id: None for s in syncs}

    def _build_sync_data_list(
        self,
        syncs: List[Sync],
        sync_connections: Dict[UUID, Dict[str, Any]],
        source_conn_map: Dict[UUID, Dict[str, Any]],
        last_job_map: Dict[UUID, Dict[str, Any]],
        all_tags_map: Dict[UUID, List[str]],
        entity_count_map: Dict[UUID, int],
        arf_count_map: Dict[UUID, Optional[int]],
        qdrant_count_map: Dict[UUID, Optional[int]],
        vespa_count_map: Dict[UUID, Optional[int]],
    ) -> List[Dict[str, Any]]:
        """Build response data list from fetched information."""
        sync_data_list = []

        for sync in syncs:
            conn_info = sync_connections.get(sync.id, {"source": None, "destinations": []})
            source_info = source_conn_map.get(sync.id, {})
            last_job = last_job_map.get(sync.id, {})

            sync_dict = {**sync.__dict__}
            if "_sa_instance_state" in sync_dict:
                sync_dict.pop("_sa_instance_state")

            # Enrich with metadata
            sync_dict["source_connection_id"] = conn_info["source"]
            sync_dict["destination_connection_ids"] = conn_info["destinations"]
            sync_dict["total_entity_count"] = entity_count_map.get(sync.id, 0)
            sync_dict["total_arf_entity_count"] = arf_count_map.get(sync.id)
            sync_dict["total_qdrant_entity_count"] = qdrant_count_map.get(sync.id)
            sync_dict["total_vespa_entity_count"] = vespa_count_map.get(sync.id)

            # Handle status enum
            last_status = last_job.get("status")
            sync_dict["last_job_status"] = (
                (last_status.value if hasattr(last_status, "value") else last_status)
                if last_status
                else None
            )
            sync_dict["last_job_at"] = last_job.get("completed_at")
            sync_dict["last_job_error"] = last_job.get("error")
            sync_dict["all_tags"] = all_tags_map.get(sync.id)
            sync_dict["source_short_name"] = source_info.get("short_name")
            sync_dict["readable_collection_id"] = source_info.get("readable_collection_id")
            sync_dict["source_is_authenticated"] = source_info.get("is_authenticated")

            sync_data_list.append(sync_dict)

        return sync_data_list


# Singleton instance
admin_sync_service = AdminSyncService()
