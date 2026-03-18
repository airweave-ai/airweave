"""Shared test helpers for agentic search tests."""

from __future__ import annotations

from uuid import uuid4

from airweave.adapters.llm.registry import LLMModelSpec, ThinkingConfig
from airweave.adapters.tokenizer.fakes import FakeTokenizer
from airweave.adapters.tokenizer.registry import TokenizerEncoding, TokenizerType
from airweave.core.protocols.llm import LLMResponse, LLMToolCall
from airweave.domains.search.agentic.context_manager import ContextManager
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import RenderedResult
from airweave.domains.search.types.results import (
    SearchAccessControl,
    SearchBreadcrumb,
    SearchResult,
    SearchSystemMetadata,
)


def make_result(
    entity_id: str = "ent-1",
    name: str = "Test Entity",
    score: float = 0.95,
    source_name: str = "test-source",
    entity_type: str = "TestEntity",
    chunk_index: int = 0,
    original_entity_id: str | None = None,
    content: str = "Test content here.",
) -> SearchResult:
    """Build a SearchResult with sensible defaults."""
    return SearchResult(
        entity_id=entity_id,
        name=name,
        relevance_score=score,
        breadcrumbs=[
            SearchBreadcrumb(entity_id="parent-1", name="Parent", entity_type="FolderEntity")
        ],
        textual_representation=content,
        airweave_system_metadata=SearchSystemMetadata(
            source_name=source_name,
            entity_type=entity_type,
            sync_id=str(uuid4()),
            sync_job_id=str(uuid4()),
            chunk_index=chunk_index,
            original_entity_id=original_entity_id or entity_id,
        ),
        access=SearchAccessControl(),
        web_url=f"https://example.com/{entity_id}",
        raw_source_fields={},
    )


def make_state(
    results: dict[str, SearchResult] | None = None,
    collected_ids: set[str] | None = None,
) -> AgentState:
    """Build an AgentState with optional pre-seeded data."""
    state = AgentState()
    if results:
        state.results = results
    if collected_ids:
        state.collected_ids = collected_ids
    return state


def make_context_mgr(
    context_window: int = 100_000,
    max_output_tokens: int = 20_000,
    thinking_enabled: bool = False,
    chars_per_token: int = 4,
) -> ContextManager:
    """Build a ContextManager with FakeTokenizer."""
    tokenizer = FakeTokenizer(chars_per_token=chars_per_token)
    return ContextManager(
        tokenizer=tokenizer,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        thinking_enabled=thinking_enabled,
        system_prompt="You are a search agent.",
        tools=[{"type": "function", "function": {"name": "search"}}],
    )


def make_llm_response(
    text: str | None = None,
    thinking: str | None = None,
    tool_calls: list[LLMToolCall] | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> LLMResponse:
    """Build an LLMResponse with defaults."""
    return LLMResponse(
        text=text,
        thinking=thinking,
        tool_calls=tool_calls or [],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def make_rendered_result(
    entity_id: str = "ent-1",
    text: str = "- **Test Entity** (id: ent-1, score: 0.95)\n  Summary text.",
) -> RenderedResult:
    """Build a RenderedResult for context manager tests."""
    return RenderedResult(entity_id=entity_id, text=text)


def make_model_spec(
    context_window: int = 200_000,
    max_output_tokens: int = 64_000,
) -> LLMModelSpec:
    """Build an LLMModelSpec for tests."""
    return LLMModelSpec(
        api_model_name="test-model",
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        required_tokenizer_type=TokenizerType.TIKTOKEN,
        required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
        thinking_config=ThinkingConfig(param_name="_noop", param_value=True),
    )
