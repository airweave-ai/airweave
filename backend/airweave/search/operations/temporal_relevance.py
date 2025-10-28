"""Temporal relevance operation.

Computes dynamic time-based decay configuration by analyzing the actual
time range of the (optionally filtered) collection. This enables recency-aware
ranking that respects the dataset's time distribution.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

from pydantic import BaseModel
from qdrant_client.http import models as rest

from airweave.api.context import ApiContext
from airweave.search.context import SearchContext

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.platform.destinations.qdrant import QdrantDestination


class DecayConfig(BaseModel):
    """Configuration for time-based decay in Qdrant queries."""

    decay_type: str  # "linear", "exponential", "gaussian"
    datetime_field: str
    target_datetime: datetime
    scale_seconds: float
    midpoint: float
    weight: float

    def get_scale_seconds(self) -> float:
        """Get scale in seconds for decay calculation."""
        return self.scale_seconds


class TemporalRelevance(SearchOperation):
    """Compute dynamic temporal decay configuration for recency-aware search."""

    DATETIME_FIELD = "updated_at"  # Primary timestamp field (fallback to created_at in extraction)
    DECAY_TYPE = "linear"
    MIDPOINT = 0.5

    def __init__(self, weight: float, supporting_sources: Optional[List[str]] = None) -> None:
        """Initialize with temporal relevance weight and list of supporting sources.

        Args:
            weight: Temporal relevance weight (0-1)
            supporting_sources: Optional list of source short_names to filter to.
                - Non-empty list: Only include documents from these sources
                - None: No source filtering (all sources included)
                - Empty list is never passed (factory skips operation entirely)
        """
        self.weight = weight
        self.supporting_sources = supporting_sources

    def depends_on(self) -> List[str]:
        """Depends on filter operations."""
        return ["QueryInterpretation", "UserFilter"]

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Compute decay configuration from collection timestamps."""
        ctx.logger.debug(
            "[TemporalRelevance] Computing decay configuration from collection timestamps"
        )

        # Emit recency start
        emit_data = {"requested_weight": self.weight}
        if self.supporting_sources is not None:
            emit_data["supporting_sources"] = self.supporting_sources
            emit_data["source_filtering_enabled"] = True
        await context.emitter.emit(
            "recency_start",
            emit_data,
            op_name=self.__class__.__name__,
        )

        # Get filter from state if available (respects filtered timespan)
        filter_dict = state.get("filter")
        qdrant_filter = self._convert_to_qdrant_filter(filter_dict)

        # Inject tenant filter for multi-tenant isolation
        tenant_condition = rest.FieldCondition(
            key="airweave_collection_id",
            match=rest.MatchValue(value=str(context.collection_id)),
        )

        # CRITICAL: Filter to only documents with updated_at field
        # This prevents Qdrant decay formula errors on documents without timestamps
        # IsEmpty matches: field doesn't exist OR is null OR is []
        # We use must_not to require: field exists AND has a value
        has_timestamp_condition = rest.IsEmptyCondition(
            is_empty=rest.PayloadField(key=self.DATETIME_FIELD)
        )

        # Build must conditions list
        must_conditions = [tenant_condition]

        # Add source filter if we're restricting to temporal-supporting sources
        if self.supporting_sources is not None:
            source_condition = rest.FieldCondition(
                key="airweave_system_metadata.source_name",
                match=rest.MatchAny(any=self.supporting_sources),
            )
            must_conditions.append(source_condition)
            ctx.logger.info(
                f"[TemporalRelevance] Filtering to {len(self.supporting_sources)} "
                f"temporal-supporting source(s): {self.supporting_sources}"
            )

        if qdrant_filter:
            # Merge with existing filter
            if not qdrant_filter.must:
                qdrant_filter.must = []
            qdrant_filter.must.extend(must_conditions)
            # Ensure documents have the timestamp field for decay calculation
            if not qdrant_filter.must_not:
                qdrant_filter.must_not = []
            qdrant_filter.must_not.append(has_timestamp_condition)
        else:
            # Create new filter with tenant, source, and timestamp requirements
            qdrant_filter = rest.Filter(must=must_conditions, must_not=[has_timestamp_condition])

        ctx.logger.debug(
            f"[TemporalRelevance] Applied tenant filter: collection_id={context.collection_id}"
        )

        # Connect to Qdrant (runtime import to avoid circular dependency)
        from airweave.platform.destinations.qdrant import QdrantDestination

        destination = await QdrantDestination.create(
            collection_id=context.collection_id,
            vector_size=context.vector_size,
            logger=ctx.logger,
        )

        # First, check if the filtered search space has any documents
        document_count = await self._count_filtered_documents(destination, qdrant_filter)
        ctx.logger.debug(f"[TemporalRelevance] Filtered document count: {document_count}")

        if document_count == 0:
            await context.emitter.emit(
                "recency_skipped",
                {"reason": "no_documents_in_filtered_space"},
                op_name=self.__class__.__name__,
            )
            ctx.logger.warning("[TemporalRelevance] No documents found in filtered search space. ")
            return

        # Get oldest and newest timestamps
        oldest, newest = await self._get_min_max_timestamps(destination, qdrant_filter)
        ctx.logger.debug(f"[TemporalRelevance] Oldest timestamp: {oldest}")
        ctx.logger.debug(f"[TemporalRelevance] Newest timestamp: {newest}")

        if not oldest or not newest:
            await context.emitter.emit(
                "recency_skipped",
                {"reason": "no_valid_timestamps"},
                op_name=self.__class__.__name__,
            )
            ctx.logger.warning(
                f"[TemporalRelevance] Could not find valid timestamps in "
                f"{document_count} documents. Skipping temporal relevance calculation."
            )
            # Don't fail - just skip temporal relevance
            return

        if newest <= oldest:
            await context.emitter.emit(
                "recency_skipped",
                {"reason": "invalid_range"},
                op_name=self.__class__.__name__,
            )
            raise ValueError(
                f"Invalid time range: newest ({newest}) <= oldest ({oldest}). "
                "Cannot compute temporal decay."
            )

        # Calculate scale as full time span for linear decay
        scale_seconds = (newest - oldest).total_seconds()

        if scale_seconds <= 0:
            await context.emitter.emit(
                "recency_skipped",
                {"reason": "zero_span"},
                op_name=self.__class__.__name__,
            )
            raise ValueError(f"Time span is zero or negative: {scale_seconds} seconds")

        # Emit time span details
        await context.emitter.emit(
            "recency_span",
            {
                "field": self.DATETIME_FIELD,
                "oldest": oldest.isoformat(),
                "newest": newest.isoformat(),
                "span_seconds": scale_seconds,
            },
            op_name=self.__class__.__name__,
        )

        # Build decay config
        decay_config = DecayConfig(
            decay_type=self.DECAY_TYPE,
            datetime_field=self.DATETIME_FIELD,
            target_datetime=newest,  # Use newest item time, not current time
            scale_seconds=scale_seconds,
            midpoint=self.MIDPOINT,
            weight=self.weight,
        )
        ctx.logger.debug(f"[TemporalRelevance] Decay config: {decay_config}")

        # Write to state - includes both decay config AND updated filter with timestamp requirement
        state["decay_config"] = decay_config

        # CRITICAL: Update the filter in state to exclude documents without timestamps
        # This ensures Retrieval operation only searches documents compatible with decay formula
        filter_with_timestamp = self._build_filter_excluding_null_timestamps(filter_dict)
        state["filter"] = filter_with_timestamp
        ctx.logger.debug(
            f"[TemporalRelevance] Updated filter to require {self.DATETIME_FIELD} field "
            "for decay calculation"
        )

    def _build_filter_excluding_null_timestamps(self, filter_dict: Optional[dict]) -> dict:
        """Build filter that excludes documents without updated_at field.

        This is critical for temporal decay - Qdrant's decay formulas fail on
        documents without the timestamp field. By filtering them out, we ensure
        only timestamped documents are included in temporal relevance searches.

        Also applies source filtering if supporting_sources is set.

        Args:
            filter_dict: Existing filter dict from state (may be None)

        Returns:
            Filter dict with must_not condition to exclude empty/missing timestamps
            and must condition to restrict to supporting sources if applicable
        """
        # Build the IsEmpty condition to exclude documents without timestamps
        # IsEmpty matches: field doesn't exist OR field is null OR field is []
        # We use must_not to invert it: field exists AND has a value
        is_empty_condition = {"is_empty": {"key": self.DATETIME_FIELD}}

        # Start with existing filter or empty dict
        updated_filter = filter_dict.copy() if filter_dict else {}

        # Add timestamp exclusion to must_not conditions
        if "must_not" not in updated_filter:
            updated_filter["must_not"] = []
        updated_filter["must_not"].append(is_empty_condition)

        # Add source filter if we're restricting to temporal-supporting sources
        if self.supporting_sources is not None:
            source_condition = {
                "key": "airweave_system_metadata.source_name",
                "match": {"any": self.supporting_sources},
            }
            if "must" not in updated_filter:
                updated_filter["must"] = []
            updated_filter["must"].append(source_condition)

        return updated_filter

    def _convert_to_qdrant_filter(self, filter_dict: Optional[dict]) -> Optional[rest.Filter]:
        """Convert filter dict to Qdrant Filter object."""
        if not filter_dict:
            return None

        try:
            return rest.Filter.model_validate(filter_dict)
        except Exception as e:
            raise ValueError(f"Invalid filter format for Qdrant: {e}") from e

    async def _count_filtered_documents(
        self,
        destination: "QdrantDestination",
        qdrant_filter: Optional[rest.Filter],
    ) -> int:
        """Count documents in the filtered search space."""
        try:
            # Use scroll with limit=1 to check if any documents exist
            # This is more efficient than counting all documents
            result = await destination.client.scroll(
                collection_name=destination.collection_name,
                limit=1,
                scroll_filter=qdrant_filter,
                with_payload=False,
                with_vectors=False,
            )

            # If we got any points, the collection is not empty
            if result and result[0]:
                # For efficiency, we don't need exact count, just non-zero
                # We could do a full count, but that's expensive for large collections
                return 1  # Return 1 to indicate "has documents"
            return 0
        except Exception as e:
            # If count fails, assume collection might have documents and continue
            # This ensures we don't fail temporal relevance due to count errors
            raise RuntimeError(f"Failed to check document count: {e}") from e

    async def _get_min_max_timestamps(
        self,
        destination: "QdrantDestination",
        qdrant_filter: Optional[rest.Filter],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Fetch oldest and newest timestamps using ordered scrolls."""
        # Get oldest (fetch both updated_at and created_at for fallback)
        oldest_points = await destination.client.scroll(
            collection_name=destination.collection_name,
            limit=1,
            with_payload=[self.DATETIME_FIELD, "created_at"],
            order_by=rest.OrderBy(key=self.DATETIME_FIELD, direction="asc"),
            scroll_filter=qdrant_filter,
        )

        # Get newest (fetch both updated_at and created_at for fallback)
        newest_points = await destination.client.scroll(
            collection_name=destination.collection_name,
            limit=1,
            with_payload=[self.DATETIME_FIELD, "created_at"],
            order_by=rest.OrderBy(key=self.DATETIME_FIELD, direction="desc"),
            scroll_filter=qdrant_filter,
        )

        oldest = self._extract_datetime(oldest_points)
        newest = self._extract_datetime(newest_points)

        return oldest, newest

    def _extract_datetime(self, scroll_result: tuple) -> Optional[datetime]:
        """Extract datetime from Qdrant scroll result."""
        if not scroll_result or not scroll_result[0]:
            return None

        point = scroll_result[0][0]
        if not point or not hasattr(point, "payload"):
            return None

        # Get timestamp directly from payload (entity-level field)
        payload = point.payload

        # Try updated_at first, fallback to created_at
        value = payload.get(self.DATETIME_FIELD)
        if value is None:
            value = payload.get("created_at")

        # Parse datetime and ensure timezone-aware
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                # Ensure timezone-aware - fromisoformat may return naive datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                return None
        elif isinstance(value, datetime):
            # Ensure timezone-aware datetime
            if value.tzinfo is None:
                # Assume UTC for naive datetimes
                return value.replace(tzinfo=timezone.utc)
            return value

        return None
