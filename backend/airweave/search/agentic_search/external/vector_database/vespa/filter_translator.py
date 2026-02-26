"""Filter translator for AgenticSearchPlan filter_groups → Vespa YQL.

Converts agentic_search filter groups to Vespa YQL WHERE clause components.
Handles conversion from dot notation to Vespa underscore format.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union

from airweave.core.logging import ContextualLogger
from airweave.search.agentic_search.schemas.filter import (
    AgenticSearchFilterCondition,
    AgenticSearchFilterGroup,
    AgenticSearchFilterOperator,
)


class FilterTranslationError(Exception):
    """Raised when filter translation fails."""

    pass


class FilterTranslator:
    """Translates AgenticSearchPlan filter_groups to Vespa YQL.

    Handles the conversion of AgenticSearchFilterGroup/AgenticSearchFilterCondition format
    to Vespa YQL WHERE clause components.

    Logic:
    - Conditions within a group: combined with AND
    - Multiple groups: combined with OR
    - Result: (A AND B) OR (C AND D) OR ...

    Usage:
        translator = FilterTranslator(logger=ctx.logger)
        yql_clause = translator.translate(plan.filter_groups)
        # Returns: "(field1 = 'value1' AND field2 > 100) OR (field3 contains 'text')"
    """

    def __init__(self, logger: ContextualLogger) -> None:
        """Initialize the filter translator.

        Args:
            logger: Logger for debug messages.
        """
        self._logger = logger

    def translate(self, filter_groups: List[AgenticSearchFilterGroup]) -> Optional[str]:
        """Translate filter groups to YQL WHERE clause.

        Args:
            filter_groups: List of AgenticSearchFilterGroups from the plan.

        Returns:
            YQL clause string, or None if no filters.

        Raises:
            FilterTranslationError: If a filter references a non-filterable field.
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

        self._logger.debug(f"[FilterTranslator] Translated {len(filter_groups)} filter groups")
        return result

    def _translate_group(self, group: AgenticSearchFilterGroup) -> Optional[str]:
        """Translate a single FilterGroup to YQL (AND of conditions).

        Args:
            group: AgenticSearchFilterGroup with list of conditions.

        Returns:
            YQL clause with conditions ANDed together.

        Raises:
            FilterTranslationError: If a condition uses a non-filterable field.
        """
        condition_clauses = []
        for condition in group.conditions:
            clause = self._translate_condition(condition)
            condition_clauses.append(clause)

        if not condition_clauses:
            return None

        return " AND ".join(condition_clauses)

    def _translate_condition(self, condition: AgenticSearchFilterCondition) -> str:
        """Translate a single FilterCondition to YQL.

        Converts dot notation to Vespa underscore format for system metadata fields.
        Breadcrumb fields keep dot notation (Vespa struct-field syntax).

        Args:
            condition: AgenticSearchFilterCondition with field, operator, value.

        Returns:
            YQL clause for this condition.
        """
        # Get string value from enum and convert to Vespa format
        field_str = condition.field.value
        vespa_field = self._to_vespa_field_name(field_str)

        operator = condition.operator
        value = condition.value

        # Convert datetime strings to epoch for timestamp fields (fields ending in _at)
        if self._is_datetime_field(field_str) and isinstance(value, str):
            value = self._parse_datetime_to_epoch(value, field_str)

        # Dispatch to appropriate builder method
        return self._dispatch_operator(vespa_field, operator, value)

    def _to_vespa_field_name(self, field: str) -> str:
        """Convert field name to Vespa format.

        - Breadcrumb fields (breadcrumbs.x): keep as-is (Vespa struct-field syntax)
        - System metadata fields (airweave_system_metadata.x): convert dot to underscore

        Args:
            field: Field name with dot notation.

        Returns:
            Vespa field name.
        """
        if field.startswith("breadcrumbs."):
            # Breadcrumbs use Vespa struct-field dot notation
            return field
        # Convert dots to underscores for system metadata
        return field.replace(".", "_")

    def _is_datetime_field(self, field: str) -> bool:
        """Check if a field is a datetime/timestamp field.

        Vespa stores timestamps as epoch seconds, so datetime strings
        need to be converted before filtering.

        Args:
            field: Field name to check.

        Returns:
            True if field is a datetime field (ends with '_at').
        """
        return field.endswith("_at")

    def _dispatch_operator(
        self, field: str, operator: AgenticSearchFilterOperator, value: Any
    ) -> str:
        """Dispatch to the appropriate operator handler.

        Args:
            field: Vespa field name.
            operator: Filter operator.
            value: Filter value.

        Returns:
            YQL clause string.
        """
        # Comparison operators with simple formatting
        comparison_ops = {
            AgenticSearchFilterOperator.GREATER_THAN: ">",
            AgenticSearchFilterOperator.LESS_THAN: "<",
            AgenticSearchFilterOperator.GREATER_THAN_OR_EQUAL: ">=",
            AgenticSearchFilterOperator.LESS_THAN_OR_EQUAL: "<=",
        }
        if operator in comparison_ops:
            return f"{field} {comparison_ops[operator]} {self._format_numeric_value(value)}"

        # Complex operators with dedicated methods
        method_map = {
            AgenticSearchFilterOperator.EQUALS: self._build_equals,
            AgenticSearchFilterOperator.NOT_EQUALS: self._build_not_equals,
            AgenticSearchFilterOperator.CONTAINS: self._build_contains,
            AgenticSearchFilterOperator.IN: self._build_in,
            AgenticSearchFilterOperator.NOT_IN: self._build_not_in,
        }
        if operator in method_map:
            return method_map[operator](field, value)

        raise FilterTranslationError(f"Unknown operator: {operator}")

    def _build_equals(self, field: str, value: Union[str, int, float, bool]) -> str:
        """Build equals clause.

        For string attributes in Vespa, use contains with single quotes.
        """
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
            # Empty IN list matches nothing
            return "false"
        clauses = [f"{field} contains '{self._escape_string(v)}'" for v in values]
        return f"({' OR '.join(clauses)})"

    def _build_not_in(self, field: str, values: List) -> str:
        """Build NOT IN clause (AND of not contains)."""
        if not values:
            # Empty NOT IN matches everything
            return "true"
        clauses = [f"!({field} contains '{self._escape_string(v)}')" for v in values]
        return f"({' AND '.join(clauses)})"

    def _format_numeric_value(self, value: Union[int, float]) -> str:
        """Format a numeric value for YQL comparison."""
        return str(value)

    def _escape_string(self, value: str) -> str:
        """Escape special characters for YQL string literals.

        Args:
            value: String value to escape.

        Returns:
            Escaped string safe for YQL (single-quoted).
        """
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _parse_datetime_to_epoch(self, value: str, field: str) -> int:
        """Parse ISO datetime string to epoch seconds.

        Args:
            value: ISO format datetime string (e.g., "2024-01-01T00:00:00Z").
            field: Field name for error messages.

        Returns:
            Epoch seconds (int).

        Raises:
            FilterTranslationError: If datetime parsing fails.
        """
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp())
        except (ValueError, AttributeError) as e:
            raise FilterTranslationError(
                f"Failed to parse datetime '{value}' for field '{field}': {e}"
            ) from e
