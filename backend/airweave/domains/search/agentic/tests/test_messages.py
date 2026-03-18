"""Tests for message formatting functions."""

from airweave.core.protocols.llm import LLMResponse, LLMToolCall
from airweave.domains.search.agentic.messages import (
    build_assistant_message,
    build_system_prompt,
    build_tool_result_message,
    build_user_message,
)
from airweave.domains.search.types.metadata import CollectionMetadata


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_contains_metadata(self) -> None:
        metadata = CollectionMetadata(
            collection_id="col-1",
            collection_readable_id="test-col",
            sources=[],
        )
        result = build_system_prompt(metadata, max_iterations=15)
        assert "test-col" in result
        assert "15" in result

    def test_contains_overview_and_task(self) -> None:
        metadata = CollectionMetadata(
            collection_id="col-1",
            collection_readable_id="test-col",
            sources=[],
        )
        result = build_system_prompt(metadata, max_iterations=10)
        assert "Airweave" in result
        assert len(result) > 500  # should be substantial


class TestBuildUserMessage:
    """Tests for build_user_message."""

    def test_basic_query(self) -> None:
        msg = build_user_message("find documents about AI", [])
        assert msg["role"] == "user"
        assert "find documents about AI" in msg["content"]
        assert "None" in msg["content"]  # no filters

    def test_with_filters(self) -> None:
        from airweave.domains.search.types.filters import (
            FilterableField,
            FilterCondition,
            FilterGroup,
            FilterOperator,
        )

        filters = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.SYSTEM_METADATA_SOURCE_NAME,
                        operator=FilterOperator.EQUALS,
                        value="slack",
                    )
                ]
            )
        ]
        msg = build_user_message("test", filters)
        assert "slack" in msg["content"]


class TestBuildAssistantMessage:
    """Tests for build_assistant_message."""

    def test_text_only(self) -> None:
        response = LLMResponse(text="I'll search now.", thinking=None, tool_calls=[])
        msg = build_assistant_message(response)
        assert msg["role"] == "assistant"
        assert msg["content"] == "I'll search now."
        assert "_thinking" in msg
        assert msg["_thinking"] is None

    def test_with_thinking(self) -> None:
        response = LLMResponse(
            text="Let me search.", thinking="I should look for...", tool_calls=[]
        )
        msg = build_assistant_message(response)
        assert msg["_thinking"] == "I should look for..."
        assert msg["content"] == "Let me search."

    def test_with_tool_calls(self) -> None:
        tc = LLMToolCall(id="tc-1", name="search", arguments={"query": {"primary": "test"}})
        response = LLMResponse(text=None, thinking=None, tool_calls=[tc])
        msg = build_assistant_message(response)
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["id"] == "tc-1"
        assert msg["tool_calls"][0]["function"]["name"] == "search"

    def test_empty_response(self) -> None:
        response = LLMResponse(text=None, thinking=None, tool_calls=[])
        msg = build_assistant_message(response)
        assert msg["content"] is None
        assert "tool_calls" not in msg


class TestBuildToolResultMessage:
    """Tests for build_tool_result_message."""

    def test_basic(self) -> None:
        msg = build_tool_result_message("tc-1", "search", "5 results found")
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "tc-1"
        assert msg["content"] == "5 results found"
        assert msg["_tool_name"] == "search"
