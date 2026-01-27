"""Pydantic schemas for the search planner's structured output."""

from enum import Enum
from typing import List, Union

from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
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


class RetrievalStrategy(str, Enum):
    """Supported retrieval strategies."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class FilterCondition(BaseModel):
    """A single filter condition.

    Examples:
        - {"field": "source_name", "operator": "equals", "value": "notion"}
        - {"field": "entity_type", "operator": "in", "value": ["SlackMessageEntity", ...]}
        - {"field": "created_at", "operator": "greater_than", "value": "2024-01-01T00:00:00Z"}
    """

    field: str = Field(
        description="The field name to filter on (e.g., 'source_name', 'entity_type', 'created_at')"
    )
    operator: FilterOperator = Field(description="The comparison operator to use")
    value: Union[str, int, float, bool, List[str], List[int]] = Field(
        description="The value to compare against. Use a list for 'in' and 'not_in' operators."
    )


class FilterGroup(BaseModel):
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

    conditions: List[FilterCondition] = Field(
        min_length=1,
        description="Filter conditions within this group, combined with AND",
    )


class SearchPlan(BaseModel):
    """The search planner's output - a complete search plan.

    This schema defines what the planner LLM must output. The builder will
    convert this plan into a YQL query for Vespa.
    """

    queries: List[str] = Field(
        min_length=1,
        max_length=5,
        description=(
            "1-5 search queries to execute. All queries are searched semantically. "
            "Only the first query is also used for keyword/BM25 matching. "
            "Put your best keyword-optimized query first."
        ),
    )
    filter_groups: List[FilterGroup] = Field(
        default_factory=list,
        description=(
            "Filter groups to narrow the search space. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR. "
            "Leave empty for no filtering."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        description="Maximum number of results to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip (for pagination)",
    )
    retrieval_strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID,
        description=(
            "The retrieval strategy: 'semantic' for vector similarity, "
            "'keyword' for BM25 text matching, 'hybrid' for both combined"
        ),
    )
    reasoning: str = Field(
        description=(
            "Explain your search plan: why these queries, filters, and strategy? "
            "What are you trying to find and why do you think this approach will work?"
        ),
    )
