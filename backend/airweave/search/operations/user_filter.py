"""User filter operation.

Applies user-provided filters and merges them with filters extracted
from query interpretation. Responsible for creating the final filter that
will be passed to the retrieval operation.

Accepts Airweave canonical filter dicts (Dict[str, Any] with must/should/must_not structure).
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.schemas.search import AirweaveFilter
from airweave.search.context import SearchContext

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.search.state import SearchState


class UserFilter(SearchOperation):
    """Merge user-provided filter with extracted filters."""

    # Boolean group keys for filter structure
    FILTER_KEY_MUST = "must"
    FILTER_KEY_MUST_NOT = "must_not"
    FILTER_KEY_SHOULD = "should"
    FILTER_KEY_MIN_SHOULD_MATCH = "minimum_should_match"

    # FieldCondition keys (used for detecting bare conditions)
    FIELD_CONDITION_KEY = "key"
    FIELD_CONDITION_MATCH = "match"
    FIELD_CONDITION_RANGE = "range"

    # System metadata path prefix
    SYSTEM_METADATA_PREFIX = "airweave_system_metadata."

    # System metadata fields that need path mapping (same as QueryInterpretation)
    NESTED_SYSTEM_FIELDS = {
        "source_name",
        "entity_type",
        "sync_id",
    }

    # Note: created_at, updated_at are entity-level fields (not nested in airweave_system_metadata)
    # They don't need path mapping - used directly in filters

    def __init__(self, filter: Optional[AirweaveFilter]) -> None:
        """Initialize with user-provided filter.

        Args:
            filter: Filter in Airweave canonical format (dict with must/should/must_not)
        """
        self.filter = filter

    def depends_on(self) -> List[str]:
        """Depends on operations that may write to state["filter"].

        Reads from state:
        - state["filter"] from QueryInterpretation or AccessControlFilter (if ran)
        """
        return ["QueryInterpretation", "AccessControlFilter"]

    async def execute(
        self,
        context: SearchContext,
        state: "SearchState",
        ctx: ApiContext,
    ) -> None:
        """Merge user filter with existing filter in state.

        The existing filter may include:
        - Access control filter (from AccessControlFilter)
        - Extracted filter (from QueryInterpretation)
        """
        ctx.logger.debug("[UserFilter] Applying user filter")

        # Get existing filter from state (may include access control + extracted filters)
        existing_filter = state.filter
        ctx.logger.debug(f"[UserFilter] Existing filter: {existing_filter}")

        # Normalize user filter to dict and map keys
        user_filter_dict = self._normalize_user_filter()
        ctx.logger.debug(f"[UserFilter] User filter dict: {user_filter_dict}")

        # Merge user filter with existing filter using AND semantics
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

        # Write final filter to state
        state.filter = merged_filter

        # Emit filter applied
        if merged_filter:
            has_access_control = state.access_principals is not None
            await context.emitter.emit(
                "filter_applied",
                {"filter": merged_filter, "has_access_control": has_access_control},
                op_name=self.__class__.__name__,
            )

    def _normalize_user_filter(self) -> Optional[Dict[str, Any]]:
        """Normalize user filter and map field names to destination paths.

        Handles Pydantic models (with .model_dump()) and plain dicts.

        Raises:
            HTTPException: 422 if filter format is invalid
        """
        if not self.filter:
            return None

        # Convert to dict if it's a Pydantic model
        if hasattr(self.filter, "model_dump"):
            filter_dict = self.filter.model_dump(exclude_none=True)
        elif isinstance(self.filter, dict):
            filter_dict = self.filter.copy()  # Don't mutate the original
        else:
            # Unknown type - try to use as-is
            filter_dict = dict(self.filter)

        # Validate filter structure
        self._validate_filter_structure(filter_dict)

        # Map field names in conditions
        return self._map_filter_keys(filter_dict)

    def _validate_filter_structure(self, filter_dict: Dict[str, Any]) -> None:
        """Validate that filter dict has correct structure.

        Checks that the filter uses boolean group wrappers (must/should/must_not)
        and is not a bare FieldCondition.

        Args:
            filter_dict: The filter dictionary to validate

        Raises:
            HTTPException: 422 Unprocessable Entity if filter structure is invalid
        """
        if not filter_dict:
            return

        valid_top_level_keys = {
            self.FILTER_KEY_MUST,
            self.FILTER_KEY_MUST_NOT,
            self.FILTER_KEY_SHOULD,
            self.FILTER_KEY_MIN_SHOULD_MATCH,
        }

        # Check if this looks like a bare FieldCondition instead of a filter
        if (
            self.FIELD_CONDITION_KEY in filter_dict
            or self.FIELD_CONDITION_MATCH in filter_dict
            or self.FIELD_CONDITION_RANGE in filter_dict
        ):
            example_filter = {
                self.FILTER_KEY_MUST: [
                    {
                        self.FIELD_CONDITION_KEY: "source_name",
                        self.FIELD_CONDITION_MATCH: {"value": "github"},
                    }
                ]
            }
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid filter format: received bare FieldCondition which must be "
                    f"wrapped in '{self.FILTER_KEY_MUST}', '{self.FILTER_KEY_SHOULD}', "
                    f"or '{self.FILTER_KEY_MUST_NOT}'. "
                    f"Received: {filter_dict}. "
                    f"Example of correct format: {example_filter}"
                ),
            )

        # Validate that top-level keys are recognized
        unknown_keys = set(filter_dict.keys()) - valid_top_level_keys
        if unknown_keys:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid filter format: unknown top-level keys {unknown_keys}. "
                    f"Allowed keys: {valid_top_level_keys}"
                ),
            )

        # Validate that boolean group values are lists
        for group_key in (self.FILTER_KEY_MUST, self.FILTER_KEY_MUST_NOT, self.FILTER_KEY_SHOULD):
            if group_key in filter_dict and not isinstance(filter_dict[group_key], list):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid filter format: '{group_key}' must be a list of conditions",
                )

    def _map_filter_keys(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively map field names in filter dict to destination paths."""
        if not filter_dict:
            return filter_dict

        mapped = {}
        boolean_groups = (self.FILTER_KEY_MUST, self.FILTER_KEY_MUST_NOT, self.FILTER_KEY_SHOULD)

        # Handle boolean groups (must, must_not, should)
        for group_key in boolean_groups:
            if group_key in filter_dict and isinstance(filter_dict[group_key], list):
                mapped[group_key] = [
                    self._map_condition_keys(cond) for cond in filter_dict[group_key]
                ]

        # Preserve other keys (like minimum_should_match)
        for key in filter_dict:
            if key not in boolean_groups:
                mapped[key] = filter_dict[key]

        return mapped

    def _map_condition_keys(self, condition: Dict[str, Any]) -> Dict[str, Any]:
        """Map field names in a single condition."""
        if not isinstance(condition, dict):
            return condition

        mapped = dict(condition)

        # Map the "key" field if present
        key_field = self.FIELD_CONDITION_KEY
        if key_field in mapped and isinstance(mapped[key_field], str):
            mapped[key_field] = self._map_to_destination_path(mapped[key_field])

        # Recursively handle nested boolean groups
        for group_key in (self.FILTER_KEY_MUST, self.FILTER_KEY_MUST_NOT, self.FILTER_KEY_SHOULD):
            if group_key in mapped and isinstance(mapped[group_key], list):
                mapped[group_key] = [self._map_condition_keys(c) for c in mapped[group_key]]

        return mapped

    def _map_to_destination_path(self, key: str) -> str:
        """Map field names to destination payload paths."""
        # Already has prefix
        if key.startswith(self.SYSTEM_METADATA_PREFIX):
            return key

        # Needs prefix
        if key in self.NESTED_SYSTEM_FIELDS:
            return f"{self.SYSTEM_METADATA_PREFIX}{key}"

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
            self.FILTER_KEY_MUST: (
                self._get_list(user_filter, self.FILTER_KEY_MUST)
                + self._get_list(extracted_filter, self.FILTER_KEY_MUST)
            ),
            self.FILTER_KEY_MUST_NOT: (
                self._get_list(user_filter, self.FILTER_KEY_MUST_NOT)
                + self._get_list(extracted_filter, self.FILTER_KEY_MUST_NOT)
            ),
        }

        # Handle "should" clauses
        user_should = self._get_list(user_filter, self.FILTER_KEY_SHOULD)
        extracted_should = self._get_list(extracted_filter, self.FILTER_KEY_SHOULD)

        if user_should or extracted_should:
            merged[self.FILTER_KEY_SHOULD] = user_should + extracted_should

            # If both have should clauses, require at least one from each (AND-like behavior)
            if user_should and extracted_should:
                merged[self.FILTER_KEY_MIN_SHOULD_MATCH] = 2
            else:
                merged[self.FILTER_KEY_MIN_SHOULD_MATCH] = 1

        # Remove empty lists
        return {k: v for k, v in merged.items() if v}

    def _get_list(self, filter_dict: Dict[str, Any], key: str) -> List:
        """Safely get list from filter dict."""
        value = filter_dict.get(key)
        return value if isinstance(value, list) else []
