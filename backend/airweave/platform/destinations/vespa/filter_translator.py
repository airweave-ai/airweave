"""Vespa filter translator - converts Qdrant-style filters to YQL.

Pure transformation logic with no I/O dependencies.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger

# Field name mappings from logical names to Vespa field paths
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
    # Dotted notation from QueryInterpretation (Qdrant-style)
    "airweave_system_metadata.collection_id": "airweave_system_metadata_collection_id",
    "airweave_system_metadata.entity_type": "airweave_system_metadata_entity_type",
    "airweave_system_metadata.sync_id": "airweave_system_metadata_sync_id",
    "airweave_system_metadata.sync_job_id": "airweave_system_metadata_sync_job_id",
    "airweave_system_metadata.hash": "airweave_system_metadata_hash",
    "airweave_system_metadata.original_entity_id": "airweave_system_metadata_original_entity_id",
    "airweave_system_metadata.source_name": "airweave_system_metadata_source_name",
    # Access control fields (dot notation -> flat field)
    "access.is_public": "access_is_public",
    "access.viewers": "access_viewers",
}

# Fields stored as epoch milliseconds in Vespa
EPOCH_MS_FIELDS = {"created_at", "updated_at"}


class FilterTranslator:
    """Translates Qdrant-style filter dicts to Vespa YQL clauses.

    This class handles the conversion of Airweave's canonical filter format
    (which follows Qdrant's structure) to Vespa YQL WHERE clause components.

    Filter Structure:
        - must: conditions -> AND
        - should: conditions -> OR
        - must_not: conditions -> NOT (AND)

    Condition Types:
        - FieldCondition with match -> "field contains 'value'"
        - FieldCondition with range -> comparison operators
        - FieldCondition with any -> OR across values
        - HasId -> OR across entity_ids
        - IsNull -> isNull(field) / !isNull(field)
    """

    def __init__(self, logger: Optional[ContextualLogger] = None):
        """Initialize the filter translator.

        Args:
            logger: Optional logger for debug/warning messages
        """
        self._logger = logger or default_logger

    def translate(self, filter: Optional[Dict[str, Any]]) -> Optional[str]:
        """Translate Airweave filter to Vespa YQL filter string.

        Args:
            filter: Airweave canonical filter dict (Qdrant-style)

        Returns:
            YQL filter string or None if no filter
        """
        if filter is None:
            return None

        # Handle Pydantic models for safety
        if hasattr(filter, "model_dump"):
            filter_dict = filter.model_dump(exclude_none=True)
        elif isinstance(filter, dict):
            filter_dict = filter
        else:
            self._logger.warning(f"[FilterTranslator] Unknown filter type: {type(filter)}")
            return None

        try:
            yql_clause = self._build_yql_clause(filter_dict)
            if yql_clause:
                self._logger.debug(f"[FilterTranslator] Translated filter to YQL: {yql_clause}")
            return yql_clause
        except Exception as e:
            self._logger.warning(f"[FilterTranslator] Failed to translate filter: {e}")
            return None

    def _build_yql_clause(self, filter_dict: Dict[str, Any]) -> str:
        """Build YQL WHERE clause from filter dictionary."""
        clauses = []

        # Handle 'must' conditions (AND)
        if "must" in filter_dict and filter_dict["must"]:
            must_clauses = [self._translate_condition(c) for c in filter_dict["must"]]
            must_clauses = [c for c in must_clauses if c]
            if must_clauses:
                clauses.append(f"({' AND '.join(must_clauses)})")

        # Handle 'should' conditions (OR)
        if "should" in filter_dict and filter_dict["should"]:
            should_clauses = [self._translate_condition(c) for c in filter_dict["should"]]
            should_clauses = [c for c in should_clauses if c]
            if should_clauses:
                clauses.append(f"({' OR '.join(should_clauses)})")

        # Handle 'must_not' conditions (NOT)
        if "must_not" in filter_dict and filter_dict["must_not"]:
            must_not_clauses = [self._translate_condition(c) for c in filter_dict["must_not"]]
            must_not_clauses = [c for c in must_not_clauses if c]
            if must_not_clauses:
                clauses.append(f"!({' AND '.join(must_not_clauses)})")

        return " AND ".join(clauses) if clauses else ""

    def _translate_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a single filter condition to YQL."""
        # Handle nested filter (recursive)
        if "must" in condition or "should" in condition or "must_not" in condition:
            return self._build_yql_clause(condition)

        # Handle FieldCondition with 'key' and 'match'
        if "key" in condition and "match" in condition:
            return self._translate_match_condition(condition)

        # Handle FieldCondition with 'key' and 'range'
        if "key" in condition and "range" in condition:
            return self._translate_range_condition(condition)

        # Handle HasId filter (list of IDs)
        if "has_id" in condition:
            return self._translate_has_id_condition(condition)

        # Handle is_null check (for mixed collection access control)
        if "key" in condition and "is_null" in condition:
            return self._translate_is_null_condition(condition)

        # Handle is_empty check (for empty array/field checks)
        if "key" in condition and "is_empty" in condition:
            return self._translate_is_empty_condition(condition)

        # Handle values_count (for array size checks)
        if "key" in condition and "values_count" in condition:
            return self._translate_values_count_condition(condition)

        # Handle nested condition (for array fields like breadcrumbs)
        if "nested" in condition:
            return self._translate_nested_condition(condition)

        # Fallback - return empty (will be filtered out)
        self._logger.debug(f"[FilterTranslator] Unknown condition type: {condition}")
        return ""

    def _translate_match_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a match condition to YQL."""
        key = self._map_field_name(condition["key"])
        match = condition["match"]

        # Handle "any" operator for array fields (access control filtering)
        if isinstance(match, dict) and "any" in match:
            values = match["any"]
            if not values:
                return "false"
            clauses = [f'{key} contains "{self._escape_yql_value(v)}"' for v in values]
            return f"({' OR '.join(clauses)})"

        # Handle "except" operator for exclusion (match anything EXCEPT these values)
        if isinstance(match, dict) and "except" in match:
            values = match["except"]
            if not values:
                return "true"  # Exclude nothing = match all
            clauses = [f'!({key} contains "{self._escape_yql_value(v)}")' for v in values]
            return f"({' AND '.join(clauses)})"

        # Handle simple value match
        value = match.get("value", "") if isinstance(match, dict) else match

        if isinstance(value, str):
            escaped_value = self._escape_yql_value(value)
            return f'{key} contains "{escaped_value}"'
        elif isinstance(value, bool):
            return f"{key} = {str(value).lower()}"
        elif isinstance(value, (int, float)):
            return f"{key} = {value}"
        return f'{key} contains "{value}"'

    def _translate_range_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a range condition to YQL."""
        key = self._map_field_name(condition["key"])
        range_cond = condition["range"]
        parts = []

        for op, symbol in [("gt", ">"), ("gte", ">="), ("lt", "<"), ("lte", "<=")]:
            if op in range_cond:
                value = range_cond[op]
                # Convert ISO datetime strings to epoch milliseconds for date fields
                if key in EPOCH_MS_FIELDS and isinstance(value, str):
                    value = self._parse_datetime_to_epoch_ms(value)
                parts.append(f"{key} {symbol} {value}")

        return " AND ".join(parts) if parts else ""

    def _translate_has_id_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a has_id condition to YQL."""
        ids = condition["has_id"]
        if ids:
            id_clauses = [f'entity_id contains "{id}"' for id in ids]
            return f"({' OR '.join(id_clauses)})"
        return ""

    def _translate_is_null_condition(self, condition: Dict[str, Any]) -> str:
        """Translate is_null condition to YQL."""
        key = self._map_field_name(condition["key"])
        is_null = condition["is_null"]

        if is_null:
            return f"isNull({key})"
        else:
            return f"!isNull({key})"

    def _map_field_name(self, key: str) -> str:
        """Map logical field names to Vespa field paths."""
        return FIELD_NAME_MAP.get(key, key)

    def _escape_yql_value(self, value: str) -> str:
        """Escape special characters for YQL string literals."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _parse_datetime_to_epoch_ms(self, value: str) -> int:
        """Parse ISO datetime string to epoch milliseconds."""
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp() * 1000)
        except (ValueError, AttributeError) as e:
            self._logger.warning(f"[FilterTranslator] Failed to parse datetime '{value}': {e}")
            return value

    def _translate_is_empty_condition(self, condition: Dict[str, Any]) -> str:
        """Translate is_empty condition to YQL.

        Checks whether an array field is empty or not.

        Args:
            condition: Dict with 'key' and 'is_empty' boolean

        Returns:
            YQL clause checking array size
        """
        key = self._map_field_name(condition["key"])
        is_empty = condition["is_empty"]

        if is_empty:
            # Array is empty when size = 0
            return f"size({key}) = 0"
        else:
            # Array is not empty when size > 0
            return f"size({key}) > 0"

    def _translate_values_count_condition(self, condition: Dict[str, Any]) -> str:
        """Translate values_count condition to YQL.

        Allows filtering by the number of elements in an array field.

        Args:
            condition: Dict with 'key' and 'values_count' containing gt/gte/lt/lte

        Returns:
            YQL clause checking array size against the specified constraints
        """
        key = self._map_field_name(condition["key"])
        count = condition["values_count"]
        parts = []

        for op, symbol in [("gt", ">"), ("gte", ">="), ("lt", "<"), ("lte", "<=")]:
            if op in count:
                parts.append(f"size({key}) {symbol} {count[op]}")

        return " AND ".join(parts) if parts else ""

    def _translate_nested_condition(self, condition: Dict[str, Any]) -> str:
        """Translate Qdrant nested filter for array fields like breadcrumbs.

        Nested filters allow filtering on fields within array elements.
        For example, filtering breadcrumbs by entity_id.

        Args:
            condition: Dict with 'nested' containing 'key' and 'filter'

        Returns:
            YQL clause for nested array filtering

        Example input:
            {
                "nested": {
                    "key": "breadcrumbs",
                    "filter": {
                        "must": [
                            {"key": "entity_id", "match": {"value": "some-id"}}
                        ]
                    }
                }
            }
        """
        nested = condition["nested"]
        array_key = nested["key"]  # e.g., "breadcrumbs"
        inner_filter = nested.get("filter", {})

        clauses = []

        # Process must conditions within the nested filter (AND)
        must_conditions = []
        for must_cond in inner_filter.get("must", []):
            if "key" in must_cond and "match" in must_cond:
                inner_key = must_cond["key"]
                # Build full key path: array.field (e.g., breadcrumbs.entity_id)
                full_key = f"{array_key}.{inner_key}"
                # Translate the inner match condition with the full path
                must_conditions.append(
                    self._translate_match_condition({"key": full_key, "match": must_cond["match"]})
                )
        if must_conditions:
            clauses.append(f"({' AND '.join(must_conditions)})")

        # Process should conditions (OR)
        should_conditions = []
        for should_cond in inner_filter.get("should", []):
            if "key" in should_cond and "match" in should_cond:
                inner_key = should_cond["key"]
                full_key = f"{array_key}.{inner_key}"
                should_conditions.append(
                    self._translate_match_condition(
                        {"key": full_key, "match": should_cond["match"]}
                    )
                )
        if should_conditions:
            clauses.append(f"({' OR '.join(should_conditions)})")

        if clauses:
            return f"({' AND '.join(clauses)})"
        return ""
