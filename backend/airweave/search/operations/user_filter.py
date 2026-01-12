"""User filter operation.

Applies user-provided filters and merges them with filters extracted
from query interpretation. Responsible for creating the final filter that
will be passed to the retrieval operation.

Accepts both Qdrant Filter objects and Airweave canonical filter dicts
(Dict[str, Any] with must/should/must_not structure).
"""

from typing import Any, Dict, List, Optional, Union

from airweave.api.context import ApiContext
from airweave.schemas.search import AirweaveFilter
from airweave.search.context import SearchContext

from ._base import SearchOperation

# Optional import for backwards compatibility with Qdrant Filter objects
try:
    from qdrant_client.http.models import Filter as QdrantFilter
except ImportError:
    QdrantFilter = None  # type: ignore


class UserFilter(SearchOperation):
    """Merge user-provided filter with extracted filters."""

    # System metadata fields that need path mapping (same as QueryInterpretation)
    NESTED_SYSTEM_FIELDS = {
        "source_name",
        "entity_type",
        "sync_id",
    }

    # Note: created_at, updated_at are entity-level fields (not nested in airweave_system_metadata)
    # They don't need path mapping - used directly in filters

    def __init__(self, filter: Union[AirweaveFilter, "QdrantFilter", None]) -> None:
        """Initialize with user-provided filter.

        Args:
            filter: Filter in either Airweave canonical format (dict) or Qdrant Filter object
        """
        self.filter = filter

    def depends_on(self) -> List[str]:
        """Depends on query interpretation.

        Reads from state:
        - state["filter"] from QueryInterpretation (if ran)
        """
        return ["QueryInterpretation"]

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Merge user filter with extracted filter."""
        ctx.logger.debug("[UserFilter] Applying user filter")

        # Get existing filter from state (written by QueryInterpretation if it ran)
        existing_filter = state.get("filter")
        ctx.logger.debug(f"[UserFilter] Existing filter: {existing_filter}")

        # Normalize user filter to dict and map keys
        user_filter_dict = self._normalize_user_filter()
        ctx.logger.debug(f"[UserFilter] User filter dict: {user_filter_dict}")

        # Merge filters using AND semantics
        merged_filter = self._merge_filters(user_filter_dict, existing_filter)
        ctx.logger.debug(f"[UserFilter] Merged filter: {merged_filter}")

        # Emit filter merge event if both filters present
        if existing_filter and user_filter_dict:
            await context.emitter.emit(
                "filter_merge",
                {
                    "existing": existing_filter,
                    "user": user_filter_dict,
                    "merged": merged_filter,
                },
                op_name=self.__class__.__name__,
            )

        # Write final filter to state (overwrites QueryInterpretation's filter if present)
        state["filter"] = merged_filter

        # Emit filter applied
        if merged_filter:
            await context.emitter.emit(
                "filter_applied",
                {"filter": merged_filter},
                op_name=self.__class__.__name__,
            )

    def _normalize_user_filter(self) -> Optional[Dict[str, Any]]:
        """Normalize user filter and map field names to Qdrant paths.

        Handles both Qdrant Filter objects (with .model_dump()) and plain dicts
        (Airweave canonical format).
        """
        if not self.filter:
            return None

        # Convert to dict if it's a Pydantic model (Qdrant Filter)
        if hasattr(self.filter, "model_dump"):
            filter_dict = self.filter.model_dump(exclude_none=True)
        elif isinstance(self.filter, dict):
            filter_dict = self.filter.copy()  # Don't mutate the original
        else:
            # Unknown type - try to use as-is
            filter_dict = dict(self.filter)

        # Map field names in conditions
        return self._map_filter_keys(filter_dict)

    def _map_filter_keys(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively map field names in filter dict to Qdrant paths."""
        if not filter_dict:
            return filter_dict

        mapped = {}

        # Handle boolean groups (must, must_not, should)
        for group_key in ("must", "must_not", "should"):
            if group_key in filter_dict and isinstance(filter_dict[group_key], list):
                mapped[group_key] = [
                    self._map_condition_keys(cond) for cond in filter_dict[group_key]
                ]

        # Preserve other keys (like minimum_should_match)
        for key in filter_dict:
            if key not in ("must", "must_not", "should"):
                mapped[key] = filter_dict[key]

        return mapped

    def _map_condition_keys(self, condition: Dict[str, Any]) -> Dict[str, Any]:
        """Map field names in a single condition."""
        if not isinstance(condition, dict):
            return condition

        mapped = dict(condition)

        # Map the "key" field if present
        if "key" in mapped and isinstance(mapped["key"], str):
            mapped["key"] = self._map_to_qdrant_path(mapped["key"])

        # Recursively handle nested boolean groups
        for group_key in ("must", "must_not", "should"):
            if group_key in mapped and isinstance(mapped[group_key], list):
                mapped[group_key] = [self._map_condition_keys(c) for c in mapped[group_key]]

        return mapped

    def _map_to_qdrant_path(self, key: str) -> str:
        """Map field names to Qdrant payload paths."""
        # Already has prefix
        if key.startswith("airweave_system_metadata."):
            return key

        # Needs prefix
        if key in self.NESTED_SYSTEM_FIELDS:
            return f"airweave_system_metadata.{key}"

        # Regular field, no mapping needed
        return key

    def _merge_filters(
        self, user_filter: Optional[Dict[str, Any]], extracted_filter: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Merge user and extracted filters using AND semantics."""
        # Handle None cases
        if not user_filter and not extracted_filter:
            return None
        if not user_filter:
            return extracted_filter
        if not extracted_filter:
            return user_filter

        # Both present - merge with AND semantics
        merged = {
            "must": self._get_list(user_filter, "must") + self._get_list(extracted_filter, "must"),
            "must_not": self._get_list(user_filter, "must_not")
            + self._get_list(extracted_filter, "must_not"),
        }

        # Handle "should" clauses
        user_should = self._get_list(user_filter, "should")
        extracted_should = self._get_list(extracted_filter, "should")

        if user_should or extracted_should:
            merged["should"] = user_should + extracted_should

            # If both have should clauses, require at least one from each (AND-like behavior)
            if user_should and extracted_should:
                merged["minimum_should_match"] = 2
            else:
                merged["minimum_should_match"] = 1

        # Remove empty lists
        return {k: v for k, v in merged.items() if v}

    def _get_list(self, filter_dict: Dict[str, Any], key: str) -> List:
        """Safely get list from filter dict."""
        value = filter_dict.get(key)
        return value if isinstance(value, list) else []
