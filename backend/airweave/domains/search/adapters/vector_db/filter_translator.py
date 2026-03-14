"""Filter translator for SearchPlan filter_groups → Vespa YQL.

Converts search filter groups to Vespa YQL WHERE clause components.
Handles conversion from dot notation to Vespa underscore format.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union

from airweave.core.logging import ContextualLogger
from airweave.domains.search.adapters.vector_db.exceptions import FilterTranslationError
from airweave.domains.search.types.filters import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
)


class FilterTranslator:
    """Translates SearchPlan filter_groups to Vespa YQL.

    Logic:
    - Conditions within a group: combined with AND
    - Multiple groups: combined with OR
    - Result: (A AND B) OR (C AND D) OR ...
    """

    def __init__(self, logger: ContextualLogger) -> None:
        """Initialize the filter translator."""
        self._logger = logger

    def translate(self, filter_groups: List[FilterGroup]) -> Optional[str]:
        """Translate filter groups to YQL WHERE clause.

        Args:
            filter_groups: List of FilterGroups from the plan.

        Returns:
            YQL clause string, or None if no filters.

        Raises:
            FilterTranslationError: If a filter references a non-filterable field.
        """
        if not filter_groups:
            return None

        group_clauses = []
        for group in filter_groups:
            group_yql = self._translate_group(group)
            if group_yql:
                group_clauses.append(f"({group_yql})")

        if not group_clauses:
            return None

        if len(group_clauses) == 1:
            result = group_clauses[0]
        else:
            result = " OR ".join(group_clauses)

        self._logger.debug(f"[FilterTranslator] Translated {len(filter_groups)} filter groups")
        return result

    def _translate_group(self, group: FilterGroup) -> Optional[str]:
        """Translate a single FilterGroup to YQL (AND of conditions)."""
        condition_clauses = []
        for condition in group.conditions:
            clause = self._translate_condition(condition)
            condition_clauses.append(clause)

        if not condition_clauses:
            return None

        return " AND ".join(condition_clauses)

    def _translate_condition(self, condition: FilterCondition) -> str:
        """Translate a single FilterCondition to YQL."""
        field_str = condition.field.value
        vespa_field = self._to_vespa_field_name(field_str)

        operator = condition.operator
        value = condition.value

        # Convert datetime strings to epoch for timestamp fields
        if self._is_datetime_field(field_str) and isinstance(value, str):
            value = self._parse_datetime_to_epoch(value, field_str)

        return self._dispatch_operator(vespa_field, operator, value)

    def _to_vespa_field_name(self, field: str) -> str:
        """Convert field name to Vespa format.

        - Breadcrumb fields (breadcrumbs.x): keep as-is (Vespa struct-field syntax)
        - System metadata fields (airweave_system_metadata.x): convert dot to underscore
        """
        if field.startswith("breadcrumbs."):
            return field
        return field.replace(".", "_")

    def _is_datetime_field(self, field: str) -> bool:
        """Check if a field is a datetime/timestamp field."""
        return field.endswith("_at")

    def _dispatch_operator(self, field: str, operator: FilterOperator, value: Any) -> str:
        """Dispatch to the appropriate operator handler."""
        comparison_ops = {
            FilterOperator.GREATER_THAN: ">",
            FilterOperator.LESS_THAN: "<",
            FilterOperator.GREATER_THAN_OR_EQUAL: ">=",
            FilterOperator.LESS_THAN_OR_EQUAL: "<=",
        }
        if operator in comparison_ops:
            return f"{field} {comparison_ops[operator]} {self._format_numeric_value(value)}"

        method_map = {
            FilterOperator.EQUALS: self._build_equals,
            FilterOperator.NOT_EQUALS: self._build_not_equals,
            FilterOperator.CONTAINS: self._build_contains,
            FilterOperator.IN: self._build_in,
            FilterOperator.NOT_IN: self._build_not_in,
        }
        if operator in method_map:
            return method_map[operator](field, value)

        raise FilterTranslationError(f"Unknown operator: {operator}")

    def _build_equals(self, field: str, value: Union[str, int, float, bool]) -> str:
        """Build equals clause."""
        if isinstance(value, str):
            return f"{field} contains '{self._escape_string(value)}'"
        elif isinstance(value, bool):
            return f"{field} = {str(value).lower()}"
        else:
            return f"{field} = {value}"

    def _build_not_equals(self, field: str, value: Union[str, int, float, bool]) -> str:
        """Build not equals clause."""
        if isinstance(value, str):
            return f"!({field} contains '{self._escape_string(value)}')"
        elif isinstance(value, bool):
            return f"{field} != {str(value).lower()}"
        else:
            return f"{field} != {value}"

    def _build_contains(self, field: str, value: str) -> str:
        """Build contains clause (substring match for text fields)."""
        return f"{field} contains '{self._escape_string(value)}'"

    def _build_in(self, field: str, values: List) -> str:
        """Build IN clause (OR of contains)."""
        if not values:
            return "false"
        clauses = [f"{field} contains '{self._escape_string(v)}'" for v in values]
        return f"({' OR '.join(clauses)})"

    def _build_not_in(self, field: str, values: List) -> str:
        """Build NOT IN clause (AND of not contains)."""
        if not values:
            return "true"
        clauses = [f"!({field} contains '{self._escape_string(v)}')" for v in values]
        return f"({' AND '.join(clauses)})"

    def _format_numeric_value(self, value: Union[int, float]) -> str:
        """Format a numeric value for YQL comparison."""
        return str(value)

    def _escape_string(self, value: str) -> str:
        """Escape special characters for YQL string literals."""
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _parse_datetime_to_epoch(self, value: str, field: str) -> int:
        """Parse ISO datetime string to epoch seconds."""
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp())
        except (ValueError, AttributeError) as e:
            raise FilterTranslationError(
                f"Failed to parse datetime '{value}' for field '{field}': {e}"
            ) from e
