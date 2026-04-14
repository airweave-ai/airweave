"""Tests for MistralLLM — mock the SDK client, not the network."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mistralai.models.textchunk import TextChunk
from mistralai.models.thinkchunk import ThinkChunk
from pydantic import BaseModel

from airweave.adapters.llm.exceptions import LLMProviderExhaustedError
from airweave.adapters.llm.mistral import MistralLLM
from airweave.adapters.llm.registry import LLMModelSpec, ThinkingConfig
from airweave.adapters.tokenizer.registry import TokenizerEncoding, TokenizerType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(
    thinking_param: str = "_noop",
    thinking_value: str | bool = True,
) -> LLMModelSpec:
    return LLMModelSpec(
        api_model_name="mistral-large-latest",
        context_window=256_000,
        max_output_tokens=16_384,
        required_tokenizer_type=TokenizerType.TIKTOKEN,
        required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
        thinking_config=ThinkingConfig(
            param_name=thinking_param,
            param_value=thinking_value,
        ),
    )


class _DummyOutput(BaseModel):
    key: str


def _mock_response(
    content: str | list | None = '{"key": "value"}',
    tool_calls: list | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
) -> MagicMock:
    """Build a mock mimicking the Mistral SDK ChatCompletionResponse."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.message.tool_calls = tool_calls

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = MagicMock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    return mock_resp


@pytest.fixture
def mistral_llm():
    """Instantiate MistralLLM with a patched settings object."""
    with patch("airweave.adapters.llm.mistral.settings") as mock_settings:
        mock_settings.MISTRAL_API_KEY = "test-key"
        llm = MistralLLM(model_spec=_make_spec(), max_retries=0)
        yield llm


@pytest.fixture
def mistral_llm_reasoning():
    """MistralLLM configured with reasoning_effort thinking config."""
    with patch("airweave.adapters.llm.mistral.settings") as mock_settings:
        mock_settings.MISTRAL_API_KEY = "test-key"
        llm = MistralLLM(
            model_spec=_make_spec(
                thinking_param="reasoning_effort",
                thinking_value="high",
            ),
            max_retries=0,
        )
        yield llm


# ═══════════════════════════════════════════════════════════════════════════
# structured_output tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_structured_output_returns_parsed(mistral_llm: MistralLLM) -> None:
    """_call_api parses JSON content into the Pydantic model."""
    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content='{"key": "hello"}')
    )

    result = await mistral_llm.structured_output(
        prompt="test prompt",
        schema=_DummyOutput,
        system_prompt="sys",
    )

    assert isinstance(result, _DummyOutput)
    assert result.key == "hello"


@pytest.mark.asyncio
async def test_empty_response_raises_transient(mistral_llm: MistralLLM) -> None:
    """Empty content from the API raises LLMProviderExhaustedError (wrapping transient)."""
    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content=None)
    )

    with pytest.raises(LLMProviderExhaustedError, match="empty response"):
        await mistral_llm.structured_output(
            prompt="test prompt",
            schema=_DummyOutput,
            system_prompt="sys",
        )


@pytest.mark.asyncio
async def test_structured_output_uses_json_schema(mistral_llm: MistralLLM) -> None:
    """_call_api sends json_schema response_format."""
    mock_create = AsyncMock(
        return_value=_mock_response(content='{"key": "v"}')
    )
    mistral_llm._client.chat.complete_async = mock_create

    await mistral_llm.structured_output(
        prompt="test",
        schema=_DummyOutput,
        system_prompt="sys",
    )

    call_kwargs = mock_create.call_args.kwargs
    rf = call_kwargs["response_format"]
    assert rf.type == "json_schema"
    assert rf.json_schema.strict is True


# ═══════════════════════════════════════════════════════════════════════════
# chat tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_chat_returns_tool_calls(mistral_llm: MistralLLM) -> None:
    """chat() extracts tool_calls from the response."""
    mock_tc = MagicMock()
    mock_tc.id = "tc-1"
    mock_tc.function.name = "search"
    mock_tc.function.arguments = '{"query": "hello"}'

    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content="text", tool_calls=[mock_tc])
    )

    result = await mistral_llm.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == {"query": "hello"}
    assert result.prompt_tokens == 100


@pytest.mark.asyncio
async def test_chat_dict_arguments(mistral_llm: MistralLLM) -> None:
    """chat() handles arguments already returned as dict (not stringified)."""
    mock_tc = MagicMock()
    mock_tc.id = "tc-2"
    mock_tc.function.name = "lookup"
    mock_tc.function.arguments = {"id": 42}

    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content=None, tool_calls=[mock_tc])
    )

    result = await mistral_llm.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
    )

    assert result.tool_calls[0].arguments == {"id": 42}


@pytest.mark.asyncio
async def test_chat_uses_tool_choice_any(mistral_llm: MistralLLM) -> None:
    """chat() passes tool_choice='any' to force tool usage."""
    mock_create = AsyncMock(
        return_value=_mock_response(content=None, tool_calls=None)
    )
    mistral_llm._client.chat.complete_async = mock_create

    await mistral_llm.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
    )

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["tool_choice"] == "any"


# ═══════════════════════════════════════════════════════════════════════════
# thinking/reasoning tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_chat_extracts_thinking_from_content_chunks(mistral_llm: MistralLLM) -> None:
    """chat() extracts thinking from ThinkChunk content blocks."""
    # Simulate Magistral-style response with thinking + text chunks
    think_chunk = ThinkChunk(
        thinking=[TextChunk(text="Let me reason about this...")],
        type="thinking",
    )
    text_chunk = TextChunk(text="The answer is 42", type="text")

    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content=[think_chunk, text_chunk], tool_calls=None)
    )

    result = await mistral_llm.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
    )

    assert result.thinking == "Let me reason about this..."
    assert result.text == "The answer is 42"


@pytest.mark.asyncio
async def test_chat_no_thinking_returns_none(mistral_llm: MistralLLM) -> None:
    """chat() returns thinking=None when no ThinkChunk is present."""
    mistral_llm._client.chat.complete_async = AsyncMock(
        return_value=_mock_response(content="plain text", tool_calls=None)
    )

    result = await mistral_llm.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
    )

    assert result.thinking is None
    assert result.text == "plain text"


@pytest.mark.asyncio
async def test_chat_reasoning_effort_passed(mistral_llm_reasoning: MistralLLM) -> None:
    """chat(thinking=True) passes reasoning_effort='high' for Small 4 models."""
    mock_create = AsyncMock(
        return_value=_mock_response(content=None, tool_calls=None)
    )
    mistral_llm_reasoning._client.chat.complete_async = mock_create

    await mistral_llm_reasoning.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
        thinking=True,
    )

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_chat_reasoning_effort_none_when_not_thinking(
    mistral_llm_reasoning: MistralLLM,
) -> None:
    """chat(thinking=False) passes reasoning_effort='none' for Small 4 models."""
    mock_create = AsyncMock(
        return_value=_mock_response(content=None, tool_calls=None)
    )
    mistral_llm_reasoning._client.chat.complete_async = mock_create

    await mistral_llm_reasoning.chat(
        messages=[{"role": "user", "content": "hi"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        system_prompt="sys",
        thinking=False,
    )

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["reasoning_effort"] == "none"
