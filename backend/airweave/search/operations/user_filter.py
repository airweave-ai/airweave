"""User filter operation.

Applies user-provided Qdrant filters and merges them with filters extracted
from query interpretation. Responsible for creating the final filter that
will be passed to the retrieval operation.
"""

from typing import Any, Dict, List, Optional

from qdrant_client.http.models import Filter as QdrantFilter

from airweave.api.context import ApiContext
from airweave.search.context import SearchContext

from ._base import SearchOperation


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

    def __init__(self, filter: QdrantFilter) -> None:
        """Initialize with user-provided filter."""
        self.filter = filter

    def depends_on(self) -> List[str]:
        """Depends on query interpretation (reads state["filter"] if it ran)."""
        return ["QueryInterpretation"]

    async def execute(
        self,
        context: SearchContext,
        state: dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Merge user filter with extracted filter and access control filter."""
        ctx.logger.info("[UserFilter] === STARTING ACCESS CONTROL FILTER OPERATION ===")

        # Get existing filter from state (written by QueryInterpretation if it ran)
        existing_filter = state.get("filter")
        ctx.logger.info(f"[UserFilter] Existing filter from state: {existing_filter}")

        # Build access control filter if principals provided
        access_filter = None
        if context.access_principals:
            ctx.logger.info(f"[UserFilter] Access principals provided: {context.access_principals}")
            access_filter = self._build_access_control_filter(context.access_principals)
            ctx.logger.info(
                f"[UserFilter] ✓ Access control ENABLED with "
                f"{len(context.access_principals)} principals"
            )
            ctx.logger.info(f"[UserFilter] Built access control filter: {access_filter}")
        else:
            ctx.logger.warning(
                "[UserFilter] ⚠️  NO ACCESS PRINCIPALS - All entities will be visible!"
            )

        # Normalize user filter to dict and map keys
        user_filter_dict = self._normalize_user_filter()
        ctx.logger.info(f"[UserFilter] User-provided filter (normalized): {user_filter_dict}")

        # Merge all filters using AND semantics (access + user + extracted)
        merged_filter = self._merge_all_filters(access_filter, user_filter_dict, existing_filter)
        ctx.logger.info("[UserFilter] === FINAL MERGED FILTER ===")
        ctx.logger.info(f"[UserFilter] Access filter: {access_filter}")
        ctx.logger.info(f"[UserFilter] User filter: {user_filter_dict}")
        ctx.logger.info(f"[UserFilter] Extracted filter: {existing_filter}")
        ctx.logger.info(f"[UserFilter] MERGED RESULT: {merged_filter}")

        # Emit filter merge event if multiple filters present
        if sum(x is not None for x in [existing_filter, user_filter_dict, access_filter]) > 1:
            await context.emitter.emit(
                "filter_merge",
                {
                    "access": access_filter,
                    "user": user_filter_dict,
                    "existing": existing_filter,
                    "merged": merged_filter,
                },
                op_name=self.__class__.__name__,
            )

        # Write final filter to state (overwrites QueryInterpretation's filter if present)
        state["filter"] = merged_filter
        ctx.logger.info("[UserFilter] Filter written to state for Retrieval operation")

        # Emit filter applied
        if merged_filter:
            await context.emitter.emit(
                "filter_applied",
                {"filter": merged_filter, "has_access_control": access_filter is not None},
                op_name=self.__class__.__name__,
            )

        ctx.logger.info("[UserFilter] === COMPLETED ACCESS CONTROL FILTER OPERATION ===")

    def _normalize_user_filter(self) -> Optional[Dict[str, Any]]:
        """Normalize user filter and map field names to Qdrant paths."""
        if not self.filter:
            return None

        # Convert Qdrant Filter object to dict
        filter_dict = self.filter.model_dump(exclude_none=True)

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

    def _build_access_control_filter(self, principals: List[str]) -> Dict[str, Any]:
        """Build Qdrant filter for access control.

        Returns filter that matches if:
        1. Entity is public (access.is_public = true), OR
        2. access.viewers contains ANY of the user's principals

        Args:
            principals: List of principals (e.g., ["user:john@acme.com", "group:eng"])

        Returns:
            Qdrant filter dict with should clause (OR logic between public and principals)
        """
        if not principals:
            # No access - return filter matching only public entities
            return {"must": [{"key": "access.is_public", "match": {"value": True}}]}

        # Build OR condition: public entities OR entities with matching principals
        # Use MatchAny for efficient IN operation on the viewers array
        return {
            "should": [
                # Option 1: Entity is explicitly public
                {"key": "access.is_public", "match": {"value": True}},
                # Option 2: User has matching principal in viewers array
                {"key": "access.viewers", "match": {"any": principals}},
            ]
        }

    def _merge_all_filters(
        self,
        access_filter: Optional[Dict[str, Any]],
        user_filter: Optional[Dict[str, Any]],
        extracted_filter: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Merge access control, user, and extracted filters using AND semantics.

        Logic: Results must satisfy ALL:
        - Access control (at least one principal matches) if provided
        - User filter (all conditions) if provided
        - Extracted filter (all conditions) if provided

        Args:
            access_filter: Access control filter (from principals)
            user_filter: User-provided filter
            extracted_filter: Filter extracted from query interpretation

        Returns:
            Merged filter dict or None if no filters provided
        """
        # Start with no filters
        filters_to_merge = []

        # Add each non-None filter
        if access_filter:
            filters_to_merge.append(access_filter)
        if user_filter:
            filters_to_merge.append(user_filter)
        if extracted_filter:
            filters_to_merge.append(extracted_filter)

        # Handle cases
        if len(filters_to_merge) == 0:
            return None
        if len(filters_to_merge) == 1:
            return filters_to_merge[0]

        # Multiple filters - merge with AND semantics
        # Wrap each filter in must[] to enforce AND logic between them
        return {"must": filters_to_merge}
