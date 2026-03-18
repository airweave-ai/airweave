"""Tests for SearchPlanBuilder — user filters AND'd into LLM groups."""

from airweave.domains.search.builders.search_plan import SearchPlanBuilder
from airweave.domains.search.types.filters import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
    FilterableField,
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
    """Tests for SearchPlanBuilder — user filters AND'd into LLM groups."""

    def test_no_user_filters_returns_original(self) -> None:
        """When no user filters, returns the original plan unchanged."""
        plan = _make_plan()
        result = SearchPlanBuilder.build(plan, [])
        assert result is plan

    def test_user_filter_and_into_llm_group(self) -> None:
        """User filter conditions are AND'd into each LLM filter group."""
        llm_filter = _make_filter_group(
            FilterableField.SYSTEM_METADATA_SOURCE_NAME, "slack"
        )
        plan = _make_plan(filter_groups=[llm_filter])

        user_filter = _make_filter_group(
            FilterableField.SYSTEM_METADATA_ENTITY_TYPE, "SlackMessageEntity"
        )
        result = SearchPlanBuilder.build(plan, [user_filter])

        # Still one group, but now with 2 conditions (LLM + user AND'd)
        assert len(result.filter_groups) == 1
        assert len(result.filter_groups[0].conditions) == 2

    def test_user_filter_no_llm_groups_creates_group(self) -> None:
        """When LLM has no filter groups, user conditions become a new group."""
        plan = _make_plan()

        user_filter = _make_filter_group(FilterableField.NAME, "doc1")
        result = SearchPlanBuilder.build(plan, [user_filter])

        assert len(result.filter_groups) == 1
        assert len(result.filter_groups[0].conditions) == 1

    def test_user_filter_and_into_multiple_llm_groups(self) -> None:
        """User conditions AND'd into every LLM group."""
        llm_group_a = _make_filter_group(
            FilterableField.SYSTEM_METADATA_SOURCE_NAME, "slack"
        )
        llm_group_b = _make_filter_group(
            FilterableField.SYSTEM_METADATA_SOURCE_NAME, "notion"
        )
        plan = _make_plan(filter_groups=[llm_group_a, llm_group_b])

        user_filter = _make_filter_group(
            FilterableField.SYSTEM_METADATA_ENTITY_TYPE, "MessageEntity"
        )
        result = SearchPlanBuilder.build(plan, [user_filter])

        # Still 2 groups, each now has 2 conditions
        assert len(result.filter_groups) == 2
        assert len(result.filter_groups[0].conditions) == 2
        assert len(result.filter_groups[1].conditions) == 2

    def test_user_filters_do_not_mutate_original(self) -> None:
        """User filters don't mutate the original plan."""
        plan = _make_plan()
        original_len = len(plan.filter_groups)

        user_filter = _make_filter_group(FilterableField.NAME, "doc1")
        SearchPlanBuilder.build(plan, [user_filter])

        assert len(plan.filter_groups) == original_len

    def test_plan_fields_preserved(self) -> None:
        """Non-filter fields are preserved in the result."""
        plan = _make_plan()
        user_filter = _make_filter_group(FilterableField.NAME, "doc1")
        result = SearchPlanBuilder.build(plan, [user_filter])

        assert result.query.primary == "test query"
        assert result.limit == 10
        assert result.offset == 0
        assert result.retrieval_strategy == RetrievalStrategy.HYBRID
