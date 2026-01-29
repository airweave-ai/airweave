"""Filter schemas for spotlight search."""

from enum import Enum
from typing import List, Union

from pydantic import BaseModel, Field


class SpotlightFilterOperator(str, Enum):
    """Supported filter operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"


class SpotlightFilterCondition(BaseModel):
    """A single filter condition.

    Examples:
        - {"field": "source_name", "operator": "equals", "value": "notion"}
        - {"field": "entity_type", "operator": "in", "value": ["SlackMessageEntity", ...]}
        - {"field": "created_at", "operator": "greater_than", "value": "2024-01-01T00:00:00Z"}
    """

    field: str = Field(
        ...,
        description="Field name to filter on (e.g., 'source_name', 'entity_type').",
    )
    operator: SpotlightFilterOperator = Field(..., description="The comparison operator to use.")
    value: Union[str, int, float, bool, List[str], List[int]] = Field(
        ...,
        description="Value to compare against. Use a list for 'in' and 'not_in' operators.",
    )


class SpotlightFilterGroup(BaseModel):
    """A group of filter conditions combined with AND.

    Multiple filter groups are combined with OR, allowing expressions like:
    (A AND B) OR (C AND D)

    Examples:
        Single group (AND):
            {"conditions": [
                {"field": "source_name", "operator": "equals", "value": "slack"},
                {"field": "entity_type", "operator": "equals", "value": "SlackMessageEntity"}
            ]}
            → source_name = "slack" AND entity_type = "SlackMessageEntity"

        Multiple groups (OR between groups, AND within):
            [
                {"conditions": [{"field": "source_name", "operator": "equals", "value": "slack"}]},
                {"conditions": [{"field": "source_name", "operator": "equals", "value": "notion"}]}
            ]
            → source_name = "slack" OR source_name = "notion"
    """

    conditions: List[SpotlightFilterCondition] = Field(
        ...,
        min_length=1,
        description="Filter conditions within this group, combined with AND",
    )
