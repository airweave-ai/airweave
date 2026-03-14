"""Tests for SearchPlanBuilder."""

import pytest

from airweave.domains.search.builders.search_plan import SearchPlanBuilder
from airweave.domains.search.types.filters import (
    FilterCondition,
    FilterGroup,
    FilterableField,
    FilterOperator,
)
from airweave.domains.search.types.plan import RetrievalStrategy, SearchPlan, SearchQuery


def _make_plan(filter_groups: list[FilterGroup] | None = None) -> SearchPlan:
    """Create a minimal search plan for testing."""
    return SearchPlan(
        query=SearchQuery(primary="test query"),
        filter_groups=filter_groups or [],
        limit=10,
        offset=0,
        retrieval_strategy=RetrievalStrategy.HYBRID,
    )


def _make_filter_group(field: FilterableField, value: str) -> FilterGroup:
    """Create a simple equals filter group."""
    return FilterGroup(
        conditions=[
            FilterCondition(
                field=field,
                operator=FilterOperator.EQUALS,
                value=value,
            )
        ]
    )


class TestSearchPlanBuilder:
    """Tests for SearchPlanBuilder."""

    def test_no_user_filters_returns_original(self) -> None:
        """When no user filters, returns the original plan unchanged."""
        plan = _make_plan()
        result = SearchPlanBuilder.build(plan, [])

        assert result is plan  # same object, no copy

    def test_user_filters_appended(self) -> None:
        """User filters are appended to the plan's filter_groups."""
        llm_filter = _make_filter_group(
            FilterableField.SYSTEM_METADATA_SOURCE_NAME, "slack"
        )
        plan = _make_plan(filter_groups=[llm_filter])

        user_filter = _make_filter_group(
            FilterableField.SYSTEM_METADATA_ENTITY_TYPE, "SlackMessageEntity"
        )
        result = SearchPlanBuilder.build(plan, [user_filter])

        # Result has both filters
        assert len(result.filter_groups) == 2
        assert result.filter_groups[0] == llm_filter
        assert result.filter_groups[1] == user_filter

    def test_user_filters_do_not_mutate_original(self) -> None:
        """User filters don't mutate the original plan."""
        plan = _make_plan()
        original_len = len(plan.filter_groups)

        user_filter = _make_filter_group(FilterableField.NAME, "doc1")
        SearchPlanBuilder.build(plan, [user_filter])

        # Original plan unchanged
        assert len(plan.filter_groups) == original_len

    def test_multiple_user_filters(self) -> None:
        """Multiple user filter groups are all appended."""
        plan = _make_plan()

        user_filters = [
            _make_filter_group(FilterableField.NAME, "doc1"),
            _make_filter_group(FilterableField.NAME, "doc2"),
        ]
        result = SearchPlanBuilder.build(plan, user_filters)

        assert len(result.filter_groups) == 2

    def test_plan_fields_preserved(self) -> None:
        """Non-filter fields are preserved in the result."""
        plan = _make_plan()
        user_filter = _make_filter_group(FilterableField.NAME, "doc1")
        result = SearchPlanBuilder.build(plan, [user_filter])

        assert result.query.primary == "test query"
        assert result.limit == 10
        assert result.offset == 0
        assert result.retrieval_strategy == RetrievalStrategy.HYBRID
