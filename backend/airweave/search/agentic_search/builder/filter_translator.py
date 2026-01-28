"""Filter translator for SearchPlan's filter_groups.

Converts SearchPlan filter_groups to Vespa YQL WHERE clauses.
This is separate from platform/destinations/vespa/filter_translator.py which
handles Qdrant-style filters.

Filter Groups Structure:
- FilterGroup: list of FilterConditions combined with AND
- Multiple FilterGroups: combined with OR
- Allows expressions like: (A AND B) OR (C AND D)
"""

from datetime import datetime
from typing import Any, List, Optional, Union

from airweave.api.context import ApiContext
from airweave.search.agentic_search.planner.schemas import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
)

# Field name mappings from logical names to Vespa field paths
# Reuses same mappings as the main search module for consistency
FIELD_NAME_MAP = {
    # System metadata fields (short form)
    "collection_id": "airweave_system_metadata_collection_id",
    "entity_type": "airweave_system_metadata_entity_type",
    "sync_id": "airweave_system_metadata_sync_id",
    "sync_job_id": "airweave_system_metadata_sync_job_id",
    "content_hash": "airweave_system_metadata_hash",
    "hash": "airweave_system_metadata_hash",
    "original_entity_id": "airweave_system_metadata_original_entity_id",
    "source_name": "airweave_system_metadata_source_name",
    "chunk_index": "airweave_system_metadata_chunk_index",
    # Access control fields
    "access_is_public": "access_is_public",
    "access_viewers": "access_viewers",
}

# Base fields that exist as actual Vespa schema fields (not in payload)
# These fields can be filtered on directly
BASE_VESPA_FIELDS = {
    # Entity base fields
    "entity_id",
    "name",
    "breadcrumbs",
    "created_at",
    "updated_at",
    # System metadata fields (both short and mapped names)
    "collection_id",
    "entity_type",
    "sync_id",
    "sync_job_id",
    "content_hash",
    "hash",
    "original_entity_id",
    "source_name",
    "chunk_index",
    # Access control
    "access_is_public",
    "access_viewers",
    # Content fields (for completeness, though typically not filtered)
    "textual_representation",
    "payload",
}

# Fields stored as epoch seconds in Vespa (for datetime conversion)
EPOCH_FIELDS = {"created_at", "updated_at"}


class FilterGroupTranslator:
    """Translates SearchPlan filter_groups to Vespa YQL.

    Handles the conversion of SearchPlan's FilterGroup/FilterCondition format
    to Vespa YQL WHERE clause components.

    Usage:
        translator = FilterGroupTranslator(ctx=ctx)
        yql_clause = translator.translate(plan.filter_groups)
        # Returns: "(field1 = 'value1' AND field2 > 100) OR (field3 contains 'text')"
    """

    def __init__(self, ctx: Optional[ApiContext] = None) -> None:
        """Initialize the filter translator.

        Args:
            ctx: API context for logging (optional)
        """
        self._ctx = ctx

    def _log(self, message: str, level: str = "debug") -> None:
        """Log a message if context is available."""
        if self._ctx:
            logger = getattr(self._ctx.logger, level)
            logger(f"[FilterGroupTranslator] {message}")

    def translate(self, filter_groups: List[FilterGroup]) -> Optional[str]:
        """Translate filter groups to YQL WHERE clause.

        Args:
            filter_groups: List of FilterGroups from SearchPlan

        Returns:
            YQL clause string, or None if no filters
        """
        if not filter_groups:
            return None

        # Translate each group (AND within group)
        group_clauses = []
        for group in filter_groups:
            group_yql = self._translate_group(group)
            if group_yql:
                group_clauses.append(f"({group_yql})")

        if not group_clauses:
            return None

        # Combine groups with OR
        if len(group_clauses) == 1:
            result = group_clauses[0]
        else:
            result = " OR ".join(group_clauses)

        self._log(f"Translated {len(filter_groups)} filter groups to: {result}")
        return result

    def _translate_group(self, group: FilterGroup) -> Optional[str]:
        """Translate a single FilterGroup to YQL (AND of conditions).

        Args:
            group: FilterGroup with list of conditions

        Returns:
            YQL clause with conditions ANDed together
        """
        condition_clauses = []
        for condition in group.conditions:
            clause = self._translate_condition(condition)
            if clause:
                condition_clauses.append(clause)

        if not condition_clauses:
            return None

        return " AND ".join(condition_clauses)

    def _translate_condition(self, condition: FilterCondition) -> Optional[str]:
        """Translate a single FilterCondition to YQL.

        Args:
            condition: FilterCondition with field, operator, value

        Returns:
            YQL clause for this condition, or None if field is not filterable
        """
        # Check if this is a source-specific field (stored in payload, not directly filterable)
        if not self._is_filterable_field(condition.field):
            self._log(
                f"Field '{condition.field}' is a source-specific field stored in payload. "
                f"Source fields are searchable via keywords but not directly filterable. "
                f"Consider using keyword search terms instead of filters for this field.",
                level="warning",
            )
            return None

        field = self._map_field_name(condition.field)
        operator = condition.operator
        value = condition.value

        # Convert datetime strings to epoch for date fields
        if condition.field in EPOCH_FIELDS and isinstance(value, str):
            value = self._parse_datetime_to_epoch(value)

        # Dispatch to appropriate builder method
        return self._dispatch_operator(field, operator, value)

    def _is_filterable_field(self, field: str) -> bool:
        """Check if a field can be filtered on directly in Vespa.

        Source-specific fields (like 'title', 'description', 'file_id', etc.) are stored
        in the payload JSON string and indexed for BM25 search, but they cannot be
        filtered on directly as structured fields.

        Args:
            field: The field name to check

        Returns:
            True if the field is a base/system field that can be filtered, False otherwise
        """
        # If the field is in our mapping, it's filterable
        if field in FIELD_NAME_MAP:
            return True

        # If the field is a known base Vespa field, it's filterable
        if field in BASE_VESPA_FIELDS:
            return True

        # Otherwise, it's likely a source-specific field stored in payload
        return False

    def _dispatch_operator(self, field: str, operator: FilterOperator, value: Any) -> Optional[str]:
        """Dispatch to the appropriate operator handler."""
        # Comparison operators with simple formatting
        comparison_ops = {
            FilterOperator.GREATER_THAN: ">",
            FilterOperator.LESS_THAN: "<",
            FilterOperator.GREATER_THAN_OR_EQUAL: ">=",
            FilterOperator.LESS_THAN_OR_EQUAL: "<=",
        }
        if operator in comparison_ops:
            return f"{field} {comparison_ops[operator]} {self._format_value(value)}"

        # Complex operators with dedicated methods
        method_map = {
            FilterOperator.EQUALS: self._build_equals,
            FilterOperator.NOT_EQUALS: self._build_not_equals,
            FilterOperator.CONTAINS: self._build_contains,
            FilterOperator.IN: self._build_in,
            FilterOperator.NOT_IN: self._build_not_in,
        }
        if operator in method_map:
            return method_map[operator](field, value)

        self._log(f"Unknown operator: {operator}", level="warning")
        return None

    def _build_equals(self, field: str, value: Union[str, int, float, bool]) -> str:
        """Build equals clause."""
        if isinstance(value, str):
            return f'{field} contains "{self._escape_value(value)}"'
        elif isinstance(value, bool):
            return f"{field} = {str(value).lower()}"
        else:
            return f"{field} = {value}"

    def _build_not_equals(self, field: str, value: Union[str, int, float, bool]) -> str:
        """Build not equals clause."""
        if isinstance(value, str):
            return f'!({field} contains "{self._escape_value(value)}")'
        elif isinstance(value, bool):
            return f"{field} != {str(value).lower()}"
        else:
            return f"{field} != {value}"

    def _build_contains(self, field: str, value: str) -> str:
        """Build contains clause (substring match)."""
        return f'{field} contains "{self._escape_value(value)}"'

    def _build_in(self, field: str, values: List) -> str:
        """Build IN clause (OR of equals)."""
        if not values:
            return "false"  # Empty IN list matches nothing
        clauses = [f'{field} contains "{self._escape_value(v)}"' for v in values]
        return f"({' OR '.join(clauses)})"

    def _build_not_in(self, field: str, values: List) -> str:
        """Build NOT IN clause (AND of not equals)."""
        if not values:
            return "true"  # Empty NOT IN matches everything
        clauses = [f'!({field} contains "{self._escape_value(v)}")' for v in values]
        return f"({' AND '.join(clauses)})"

    def _format_value(self, value: Union[str, int, float, bool]) -> str:
        """Format a value for YQL."""
        if isinstance(value, str):
            return f'"{self._escape_value(value)}"'
        elif isinstance(value, bool):
            return str(value).lower()
        else:
            return str(value)

    def _map_field_name(self, field: str) -> str:
        """Map logical field name to Vespa field path."""
        return FIELD_NAME_MAP.get(field, field)

    def _escape_value(self, value: str) -> str:
        """Escape special characters for YQL string literals."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _parse_datetime_to_epoch(self, value: str) -> int:
        """Parse ISO datetime string to epoch seconds.

        Args:
            value: ISO format datetime string (e.g., "2024-01-01T00:00:00Z")

        Returns:
            Epoch seconds (int)
        """
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp())
        except (ValueError, AttributeError) as e:
            self._log(f"Failed to parse datetime '{value}': {e}", level="warning")
            return value  # Return as-is if parsing fails
