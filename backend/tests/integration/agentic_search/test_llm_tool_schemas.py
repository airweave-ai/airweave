"""Integration tests for LLM tool calling with filter schemas.

Verifies that each provider:
1. Accepts the normalized tool schemas (no 400/422 validation errors)
2. Produces tool call output that parses into valid Pydantic models
3. Can generate each filter operator type when explicitly instructed

Requires API keys: set GROQ_API_KEY, CEREBRAS_API_KEY, and/or ANTHROPIC_API_KEY in env/.env.

Usage:
    pytest tests/integration/agentic_search/test_llm_tool_schemas.py -v -s
    pytest tests/integration/agentic_search/test_llm_tool_schemas.py -v -s -k groq
    pytest tests/integration/agentic_search/test_llm_tool_schemas.py -v -s -k cerebras_gpt_oss
    pytest tests/integration/agentic_search/test_llm_tool_schemas.py -v -s -k cerebras_glm
    pytest tests/integration/agentic_search/test_llm_tool_schemas.py -v -s -k anthropic
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest
import pytest_asyncio

from airweave.search.agentic_search.config import LLMModel, LLMProvider
from airweave.search.agentic_search.core.tools import SEARCH_TOOL, SUBMIT_ANSWER_TOOL
from airweave.search.agentic_search.external.llm.anthropic import AnthropicLLM
from airweave.search.agentic_search.external.llm.base import BaseLLM
from airweave.search.agentic_search.external.llm.cerebras import CerebrasLLM
from airweave.search.agentic_search.external.llm.groq import GroqLLM
from airweave.search.agentic_search.external.llm.registry import get_model_spec
from airweave.search.agentic_search.external.llm.tool_response import LLMToolResponse
from airweave.search.agentic_search.external.tokenizer.registry import TokenizerModelSpec
from airweave.search.agentic_search.external.tokenizer.tiktoken import TiktokenTokenizer
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a search assistant. When asked to search, call the search tool "
    "with the EXACT parameters specified. Follow the instructions precisely."
)

TOOLS = [SEARCH_TOOL, SUBMIT_ANSWER_TOOL]


def _make_tokenizer() -> TiktokenTokenizer:
    spec = TokenizerModelSpec(encoding_name="o200k_harmony")
    return TiktokenTokenizer(spec)


def _has_key(env_var: str) -> bool:
    return bool(os.environ.get(env_var))


# ---------------------------------------------------------------------------
# Provider-parametrized fixtures
# ---------------------------------------------------------------------------


# LLM-level retries for transient API errors (rate limits, timeouts)
LLM_MAX_RETRIES = 2


@pytest_asyncio.fixture
async def groq_llm():
    if not _has_key("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set")
    spec = get_model_spec(LLMProvider.GROQ, LLMModel.GPT_OSS_120B)
    llm = GroqLLM(spec, _make_tokenizer(), max_retries=LLM_MAX_RETRIES)
    yield llm
    await llm.close()


@pytest_asyncio.fixture
async def cerebras_llm():
    if not _has_key("CEREBRAS_API_KEY"):
        pytest.skip("CEREBRAS_API_KEY not set")
    spec = get_model_spec(LLMProvider.CEREBRAS, LLMModel.GPT_OSS_120B)
    llm = CerebrasLLM(spec, _make_tokenizer(), max_retries=LLM_MAX_RETRIES)
    yield llm
    await llm.close()


@pytest_asyncio.fixture
async def cerebras_glm_llm():
    if not _has_key("CEREBRAS_API_KEY"):
        pytest.skip("CEREBRAS_API_KEY not set")
    spec = get_model_spec(LLMProvider.CEREBRAS, LLMModel.ZAI_GLM_4_7)
    llm = CerebrasLLM(spec, _make_tokenizer(), max_retries=LLM_MAX_RETRIES)
    yield llm
    await llm.close()


@pytest_asyncio.fixture
async def anthropic_llm():
    if not _has_key("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    spec = get_model_spec(LLMProvider.ANTHROPIC, LLMModel.CLAUDE_SONNET_4_6)
    llm = AnthropicLLM(spec, _make_tokenizer(), max_retries=LLM_MAX_RETRIES)
    yield llm
    await llm.close()


# ---------------------------------------------------------------------------
# Filter operator test cases
#
# Each case: (operator, field, value_in_prompt, description)
# The prompt explicitly tells the model what to output.
# ---------------------------------------------------------------------------

SCALAR_FILTER_CASES = [
    (
        "equals",
        "airweave_system_metadata.source_name",
        "notion",
        "string equals",
    ),
    (
        "not_equals",
        "airweave_system_metadata.entity_type",
        "DraftEntity",
        "string not_equals",
    ),
    (
        "contains",
        "name",
        "quarterly report",
        "string contains",
    ),
    (
        "greater_than",
        "created_at",
        "2024-01-01T00:00:00Z",
        "date greater_than",
    ),
    (
        "less_than",
        "created_at",
        "2025-06-01T00:00:00Z",
        "date less_than",
    ),
    (
        "greater_than_or_equal",
        "updated_at",
        "2024-06-01T00:00:00Z",
        "date gte",
    ),
    (
        "less_than_or_equal",
        "updated_at",
        "2025-01-01T00:00:00Z",
        "date lte",
    ),
]

LIST_FILTER_CASES = [
    (
        "in",
        "airweave_system_metadata.source_name",
        '["notion", "slack"]',
        "string in",
    ),
    (
        "not_in",
        "airweave_system_metadata.entity_type",
        '["DraftEntity", "ArchivedEntity"]',
        "string not_in",
    ),
]

ALL_FILTER_CASES = SCALAR_FILTER_CASES + LIST_FILTER_CASES


def _build_filter_prompt(operator: str, field: str, value: str) -> str:
    """Build an explicit prompt that tells the model to use a specific filter."""
    return (
        f"Search for documents. You MUST call the search tool with these EXACT parameters:\n"
        f"- query.primary: \"test search\"\n"
        f"- query.variations: []\n"
        f"- retrieval_strategy: \"semantic\"\n"
        f"- limit: 10\n"
        f"- offset: 0\n"
        f"- filter_groups: one group with one condition:\n"
        f"  - field: \"{field}\"\n"
        f"  - operator: \"{operator}\"\n"
        f"  - value: {value}\n"
        f"\nCall the search tool now with exactly these parameters."
    )


def _print_response(response: LLMToolResponse) -> None:
    """Print full response details for debugging."""
    print(f"\n{'=' * 60}")
    print(f"  stop_reason: {response.stop_reason}")
    print(f"  text: {response.text or '(none)'}")
    print(f"  thinking: {response.thinking or '(none)'}")
    print(f"  tool_calls: {len(response.tool_calls)}")
    for i, tc in enumerate(response.tool_calls):
        print(f"  [{i}] {tc.name}:")
        print(f"      {json.dumps(tc.arguments, indent=6)}")
    print(f"  usage: {response.usage}")
    print(f"{'=' * 60}\n")


def _assert_valid_search_response(response: LLMToolResponse) -> dict[str, Any]:
    """Assert the response is a valid search tool call and return the arguments."""
    _print_response(response)
    assert response.tool_calls, f"Expected tool calls, got none. Text: {response.text}"
    tc = response.tool_calls[0]
    assert tc.name == "search", f"Expected 'search' tool call, got '{tc.name}'"
    # Validate through Pydantic — this is the real test
    plan = AgenticSearchPlan.model_validate(tc.arguments)
    print(f"  Pydantic validation OK: {len(plan.filter_groups)} filter groups")
    if plan.filter_groups:
        for gi, group in enumerate(plan.filter_groups):
            for ci, cond in enumerate(group.conditions):
                print(
                    f"    [{gi}][{ci}] {cond.field.value} "
                    f"{cond.operator.value} {cond.value!r}"
                )
    return tc.arguments


# ---------------------------------------------------------------------------
# Retry helper for stochastic model errors
# ---------------------------------------------------------------------------

MAX_RETRIES = 3


async def _call_with_retries(
    llm: BaseLLM,
    messages: list[dict],
    tools: list[dict],
    system_prompt: str,
) -> LLMToolResponse:
    """Call LLM with retries for transient model generation errors.

    LLMs are stochastic — the model may occasionally hallucinate wrong
    property names (e.g., "filters" instead of "conditions") causing
    tool_use_failed errors. These are not schema issues but generation
    misses that succeed on retry.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await llm.create_with_tools(messages, tools, system_prompt)
        except RuntimeError as e:
            if "tool_use_failed" in str(e) and attempt < MAX_RETRIES:
                print(f"  [retry {attempt}/{MAX_RETRIES}] Model generation error, retrying...")
                await asyncio.sleep(0.5)
                continue
            raise


# ---------------------------------------------------------------------------
# Groq tests
# ---------------------------------------------------------------------------


class TestGroqToolSchemas:
    """Test Groq accepts our tool schemas and produces valid output."""

    @pytest.mark.asyncio
    async def test_schema_accepted(self, groq_llm: GroqLLM):
        """Basic smoke test: Groq accepts the normalized tool schemas."""
        messages = [{"role": "user", "content": "Search for documents about cats."}]
        response = await _call_with_retries(groq_llm, messages, TOOLS, SYSTEM_PROMPT)
        assert response.tool_calls, f"No tool calls. Text: {response.text}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "operator,field,value,desc",
        SCALAR_FILTER_CASES,
        ids=[c[3] for c in SCALAR_FILTER_CASES],
    )
    async def test_scalar_filter(
        self, groq_llm: GroqLLM, operator: str, field: str, value: str, desc: str
    ):
        """Test that Groq can generate each scalar filter operator."""
        prompt = _build_filter_prompt(operator, field, value)
        messages = [{"role": "user", "content": prompt}]
        response = await _call_with_retries(groq_llm, messages, TOOLS, SYSTEM_PROMPT)
        args = _assert_valid_search_response(response)

        # Verify the filter was included
        assert args.get("filter_groups"), f"No filter_groups in response for {desc}"
        conditions = args["filter_groups"][0]["conditions"]
        assert len(conditions) >= 1, f"No conditions in filter group for {desc}"

        # Check operator matches (model should follow instructions)
        cond = conditions[0]
        assert cond["operator"] == operator, (
            f"Expected operator '{operator}', got '{cond['operator']}' for {desc}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "operator,field,value,desc",
        LIST_FILTER_CASES,
        ids=[c[3] for c in LIST_FILTER_CASES],
    )
    async def test_list_filter(
        self, groq_llm: GroqLLM, operator: str, field: str, value: str, desc: str
    ):
        """Test that Groq can generate list filter operators (in/not_in)."""
        prompt = _build_filter_prompt(operator, field, value)
        messages = [{"role": "user", "content": prompt}]
        response = await _call_with_retries(groq_llm, messages, TOOLS, SYSTEM_PROMPT)
        args = _assert_valid_search_response(response)

        assert args.get("filter_groups"), f"No filter_groups in response for {desc}"
        conditions = args["filter_groups"][0]["conditions"]
        assert len(conditions) >= 1, f"No conditions in filter group for {desc}"
        assert conditions[0]["operator"] == operator


# ---------------------------------------------------------------------------
# Cerebras GPT-OSS tests
# ---------------------------------------------------------------------------


class TestCerebrasGptOssToolSchemas:
    """Test Cerebras GPT-OSS-120B tool calling.

    Note: Cerebras does NOT enforce strict mode on tools as of March 2026.
    These tests verify the schema is accepted and the model produces parseable
    output, but the model may not follow the schema exactly.
    """

    @pytest.mark.asyncio
    async def test_schema_accepted(self, cerebras_llm: CerebrasLLM):
        """Basic smoke test: Cerebras accepts the tool schemas."""
        messages = [{"role": "user", "content": "Search for documents about cats."}]
        response = await _call_with_retries(cerebras_llm, messages, TOOLS, SYSTEM_PROMPT)
        assert response.tool_calls, f"No tool calls. Text: {response.text}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "operator,field,value,desc",
        ALL_FILTER_CASES,
        ids=[c[3] for c in ALL_FILTER_CASES],
    )
    async def test_filter(
        self,
        cerebras_llm: CerebrasLLM,
        operator: str,
        field: str,
        value: str,
        desc: str,
    ):
        """Test that Cerebras GPT-OSS can generate each filter operator."""
        prompt = _build_filter_prompt(operator, field, value)
        messages = [{"role": "user", "content": prompt}]
        response = await _call_with_retries(cerebras_llm, messages, TOOLS, SYSTEM_PROMPT)
        args = _assert_valid_search_response(response)

        assert args.get("filter_groups"), f"No filter_groups in response for {desc}"


# ---------------------------------------------------------------------------
# Cerebras ZAI-GLM-4.7 tests
# ---------------------------------------------------------------------------


class TestCerebrasGlmToolSchemas:
    """Test Cerebras ZAI-GLM-4.7 tool calling."""

    @pytest.mark.asyncio
    async def test_schema_accepted(self, cerebras_glm_llm: CerebrasLLM):
        """Basic smoke test: Cerebras GLM accepts the tool schemas."""
        messages = [{"role": "user", "content": "Search for documents about cats."}]
        response = await _call_with_retries(cerebras_glm_llm, messages, TOOLS, SYSTEM_PROMPT)
        assert response.tool_calls, f"No tool calls. Text: {response.text}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "operator,field,value,desc",
        ALL_FILTER_CASES,
        ids=[c[3] for c in ALL_FILTER_CASES],
    )
    async def test_filter(
        self,
        cerebras_glm_llm: CerebrasLLM,
        operator: str,
        field: str,
        value: str,
        desc: str,
    ):
        """Test that Cerebras GLM-4.7 can generate each filter operator."""
        prompt = _build_filter_prompt(operator, field, value)
        messages = [{"role": "user", "content": prompt}]
        response = await _call_with_retries(cerebras_glm_llm, messages, TOOLS, SYSTEM_PROMPT)
        args = _assert_valid_search_response(response)

        assert args.get("filter_groups"), f"No filter_groups in response for {desc}"


# ---------------------------------------------------------------------------
# Anthropic Claude Sonnet 4.6 tests
# ---------------------------------------------------------------------------


class TestAnthropicToolSchemas:
    """Test Anthropic Claude Sonnet 4.6 tool calling.

    Anthropic uses its native tool_use format (not OpenAI-compatible).
    The AnthropicLLM class converts between formats transparently.
    Claude Sonnet 4.6 supports adaptive thinking.
    """

    @pytest.mark.asyncio
    async def test_schema_accepted(self, anthropic_llm: AnthropicLLM):
        """Basic smoke test: Anthropic accepts the tool schemas."""
        messages = [{"role": "user", "content": "Search for documents about cats."}]
        response = await _call_with_retries(anthropic_llm, messages, TOOLS, SYSTEM_PROMPT)
        assert response.tool_calls, f"No tool calls. Text: {response.text}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "operator,field,value,desc",
        ALL_FILTER_CASES,
        ids=[c[3] for c in ALL_FILTER_CASES],
    )
    async def test_filter(
        self,
        anthropic_llm: AnthropicLLM,
        operator: str,
        field: str,
        value: str,
        desc: str,
    ):
        """Test that Anthropic Claude Sonnet 4.6 can generate each filter operator."""
        prompt = _build_filter_prompt(operator, field, value)
        messages = [{"role": "user", "content": prompt}]
        response = await _call_with_retries(anthropic_llm, messages, TOOLS, SYSTEM_PROMPT)
        args = _assert_valid_search_response(response)

        assert args.get("filter_groups"), f"No filter_groups in response for {desc}"
        conditions = args["filter_groups"][0]["conditions"]
        assert len(conditions) >= 1, f"No conditions in filter group for {desc}"
        assert conditions[0]["operator"] == operator, (
            f"Expected operator '{operator}', got '{conditions[0]['operator']}' for {desc}"
        )
