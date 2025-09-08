"""Pre-search dynamic recency bias operator.

Computes a dynamic Qdrant-side decay configuration based on the actual
time range of the (optionally filtered) collection and stores it in
context["decay_config"]. This affects recall and ranking for the whole
collection, not only the returned page, and respects user/LLM filters.

Approach:
- Determine the datetime field to use (prefer system harmonized timestamps)
- Fetch oldest and newest timestamps via two lightweight scrolls with order_by
- Compute scale_seconds as a fraction of the observed time span
- Create DecayConfig with weight = recency_bias and put it in context
- VectorSearch will pick it up and Qdrant will apply formula scoring
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as rest

from airweave.search.operations.base import SearchOperation


class RecencyBias(SearchOperation):
    """Compute dynamic DecayConfig before search and store it in context."""

    # Fraction of the data age span to use as the decay scale
    # 0.2 means the decay extends over 20% of your data's age range
    SPAN_FRACTION = 0.2

    def __init__(self, datetime_field: Optional[str] = None):
        """Initialize.

        Args:
            datetime_field: Preferred datetime field to use if available
        """
        self.datetime_field = datetime_field

    @property
    def name(self) -> str:
        """Operation name."""
        return "recency"

    @property
    def depends_on(self) -> List[str]:
        """Run after filter extraction and before vector search."""
        return ["qdrant_filter"]

    def _get_filter(self, context: Dict[str, Any]) -> Optional[rest.Filter]:
        """Build Qdrant filter from context if present."""
        if context.get("filter"):
            try:
                return rest.Filter.model_validate(context["filter"])  # type: ignore
            except Exception:
                return None
        return None

    async def _get_min_max(
        self,
        destination,
        collection_id: str,
        field: str,
        qdrant_filter: Optional[rest.Filter],
        logger,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Fetch oldest/newest timestamps using ordered scrolls."""
        logger.debug(
            f"[RecencyBias._get_min_max] Fetching min/max for field={field}, "
            f"collection={collection_id}"
        )

        # Oldest
        oldest_points = await destination.client.scroll(  # type: ignore
            collection_name=str(collection_id),
            limit=1,
            with_payload=[field],
            order_by=rest.OrderBy(key=field, direction="asc"),
            scroll_filter=qdrant_filter,
        )
        logger.debug(f"[RecencyBias._get_min_max] Oldest scroll result: {oldest_points}")

        # Newest
        newest_points = await destination.client.scroll(  # type: ignore
            collection_name=str(collection_id),
            limit=1,
            with_payload=[field],
            order_by=rest.OrderBy(key=field, direction="desc"),
            scroll_filter=qdrant_filter,
        )
        logger.debug(f"[RecencyBias._get_min_max] Newest scroll result: {newest_points}")

        def extract_dt(point) -> Optional[datetime]:
            if not point or not getattr(point, "payload", None):
                logger.debug(f"[RecencyBias.extract_dt] No point or payload: point={point}")
                return None
            value: Any = point.payload
            logger.debug(f"[RecencyBias.extract_dt] Initial payload: {value}")
            for part in field.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                    logger.debug(f"[RecencyBias.extract_dt] After getting '{part}': {value}")
                else:
                    logger.debug("[RecencyBias.extract_dt] Value not a dict, returning None")
                    return None
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    logger.debug(f"[RecencyBias.extract_dt] Parsed datetime: {dt}")
                    return dt
                except ValueError as e:
                    logger.debug(f"[RecencyBias.extract_dt] Failed to parse datetime: {e}")
                    return None
            if isinstance(value, datetime):
                logger.debug(f"[RecencyBias.extract_dt] Already datetime: {value}")
                return value
            logger.debug(f"[RecencyBias.extract_dt] Value not string or datetime: {type(value)}")
            return None

        oldest = extract_dt(oldest_points[0][0] if oldest_points and oldest_points[0] else None)
        newest = extract_dt(newest_points[0][0] if newest_points and newest_points[0] else None)
        return oldest, newest

    def _build_decay_config(
        self,
        chosen_field: str,
        t_min: datetime,
        t_max: datetime,
        recency_bias: float,
    ) -> Any:
        """Construct DecayConfig from time span and weight."""
        from airweave.search.decay import DecayConfig

        # Use the newest item's time as target, not current time
        # This ensures our actual data gets meaningful decay values
        span_seconds = max(1.0, (t_max - t_min).total_seconds())

        # Scale should cover the full data span, not just 20% of it
        # This ensures oldest items get near 0, newest get near 1
        scale_seconds = span_seconds  # Full span for linear decay

        decay_config = DecayConfig(
            decay_type="linear",
            datetime_field=chosen_field,
            target_datetime=t_max,  # Use newest item time, not now()
            scale_unit="second",
            scale_value=scale_seconds,
            midpoint=0.5,  # Not used for linear, but kept for compatibility
            weight=recency_bias,
        )

        return decay_config

    async def execute(self, context: Dict[str, Any]) -> None:
        """Compute dynamic decay from collection timestamps and store in context."""
        config = context["config"]
        logger = context["logger"]
        emitter = context.get("emit")

        # Determine weight from request via builder
        recency_bias: float = float(getattr(config, "recency_bias", 0.0) or 0.0)
        # Emit start event with requested weight
        if callable(emitter):
            try:
                await emitter(
                    "recency_start", {"requested_weight": recency_bias}, op_name=self.name
                )
            except Exception:
                pass

        if recency_bias <= 0.0:
            context["decay_config"] = None
            # Inform streaming clients we skipped due to zero weight
            if callable(emitter):
                try:
                    await emitter("recency_skipped", {"reason": "weight_zero"}, op_name=self.name)
                except Exception:
                    pass
            return

        # Determine datetime field strictly from harmonized system metadata
        # produced via AirweaveField annotations (created/updated_at).
        field = self.datetime_field or "airweave_system_metadata.airweave_updated_at"

        # Prepare Qdrant client
        from uuid import UUID

        from airweave.platform.destinations.qdrant import QdrantDestination

        destination = await QdrantDestination.create(
            collection_id=UUID(config.collection_id), logger=logger
        )

        # Query oldest/newest using the chosen field
        chosen_field: Optional[str] = None
        t_min: Optional[datetime] = None
        t_max: Optional[datetime] = None

        qdrant_filter = self._get_filter(context)

        try:
            logger.debug(f"[RecencyBias] Attempting to fetch min/max for field: {field}")
            oldest, newest = await self._get_min_max(
                destination, config.collection_id, field, qdrant_filter, logger
            )
            # Emit span details regardless of validity so UI can show what was observed
            if callable(emitter):
                try:
                    span_val = (newest - oldest).total_seconds() if (oldest and newest) else None
                    await emitter(
                        "recency_span",
                        {
                            "field": field,
                            "oldest": oldest.isoformat() if oldest else None,
                            "newest": newest.isoformat() if newest else None,
                            "span_seconds": span_val,
                        },
                        op_name=self.name,
                    )
                except Exception:
                    pass
            logger.debug(f"[RecencyBias] Got oldest={oldest}, newest={newest}")
            if oldest and newest and newest > oldest:
                chosen_field = field
                t_min, t_max = oldest, newest
                logger.info(
                    ("[RecencyBias] Field='%s', filter_applied=%s, oldest=%s, newest=%s"),
                    chosen_field,
                    bool(qdrant_filter),
                    t_min.isoformat(),
                    t_max.isoformat(),
                )
            else:
                logger.warning(
                    f"[RecencyBias] Invalid timestamps: oldest={oldest}, newest={newest}"
                )
        except Exception as e:
            logger.error(f"[RecencyBias] Error fetching min/max timestamps: {e}")
            chosen_field = None

        if not chosen_field:
            logger.info("[RecencyBias] No usable datetime field found; skipping recency bias")
            context["decay_config"] = None
            # Inform clients of skip reason
            if callable(emitter):
                try:
                    await emitter("recency_skipped", {"reason": "no_field"}, op_name=self.name)
                except Exception:
                    pass
            return

        # Build DecayConfig and store in context
        decay_config = self._build_decay_config(chosen_field, t_min, t_max, recency_bias)
        context["decay_config"] = decay_config
        logger.info(
            f"[RecencyBias] Using datetime_field='{chosen_field}', span={(t_max - t_min)}, "
            f"target=newest ({t_max.isoformat()}), "
            f"scale={decay_config.scale_value:.0f}s (full span), weight={recency_bias}"
        )
