"""Unit tests for MiniMaxLLM (agentic search provider)."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel

from airweave.search.agentic_search.config import LLMModel, LLMProvider, TokenizerEncoding, TokenizerType
from airweave.search.agentic_search.external.llm.registry import (
    LLMModelSpec,
    MODEL_REGISTRY,
    PROVIDER_API_KEY_SETTINGS,
    ReasoningConfig,
    get_model_spec,
)


# ── Test fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def minimax_model_spec():
    """Create a MiniMax model spec for testing."""
    return LLMModelSpec(
        api_model_name="MiniMax-M2.7",
        context_window=1_000_000,
        max_output_tokens=128_000,
        required_tokenizer_type=TokenizerType.TIKTOKEN,
        required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
        rate_limit_rpm=60,
        rate_limit_tpm=1_000_000,
        reasoning=ReasoningConfig(param_name="_noop", param_value=True),
    )


@pytest.fixture
def mock_tokenizer():
    """Create a mock tokenizer."""
    tokenizer = MagicMock()
    tokenizer.count_tokens = MagicMock(return_value=100)
    return tokenizer


class TestSchema(BaseModel):
    """Simple test schema for structured output."""

    name: str
    score: int


# ── Registry tests ─────────────────────────────────────────────────────


class TestMiniMaxRegistry:
    """Tests for MiniMax entries in the model registry."""

    def test_minimax_in_llm_provider_enum(self):
        """MiniMax should be a valid LLM provider."""
        assert LLMProvider.MINIMAX == "minimax"

    def test_minimax_m2_7_in_llm_model_enum(self):
        """MiniMax M2.7 should be a valid LLM model."""
        assert LLMModel.MINIMAX_M2_7 == "minimax-m2.7"

    def test_minimax_in_model_registry(self):
        """MiniMax should have entries in MODEL_REGISTRY."""
        assert LLMProvider.MINIMAX in MODEL_REGISTRY
        assert LLMModel.MINIMAX_M2_7 in MODEL_REGISTRY[LLMProvider.MINIMAX]

    def test_minimax_model_spec_values(self):
        """MiniMax model spec should have correct values."""
        spec = MODEL_REGISTRY[LLMProvider.MINIMAX][LLMModel.MINIMAX_M2_7]
        assert spec.api_model_name == "MiniMax-M2.7"
        assert spec.context_window == 1_000_000
        assert spec.max_output_tokens == 128_000

    def test_minimax_api_key_setting(self):
        """MiniMax should have an API key mapping."""
        assert LLMProvider.MINIMAX in PROVIDER_API_KEY_SETTINGS
        assert PROVIDER_API_KEY_SETTINGS[LLMProvider.MINIMAX] == "MINIMAX_API_KEY"

    def test_get_model_spec_minimax(self):
        """get_model_spec should return MiniMax spec."""
        spec = get_model_spec(LLMProvider.MINIMAX, LLMModel.MINIMAX_M2_7)
        assert spec.api_model_name == "MiniMax-M2.7"


# ── Provider initialization tests ──────────────────────────────────────


class TestMiniMaxLLMInit:
    """Tests for MiniMaxLLM initialization."""

    def test_raises_without_api_key(self, minimax_model_spec, mock_tokenizer):
        """Should raise ValueError when MINIMAX_API_KEY is not set."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = None

            from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

            with pytest.raises(ValueError, match="MINIMAX_API_KEY"):
                MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)

    def test_initializes_with_api_key(self, minimax_model_spec, mock_tokenizer):
        """Should initialize successfully with a valid API key."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-minimax-key"

            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                MockOpenAI.return_value = MagicMock()

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                assert provider is not None

                # Verify OpenAI client was created with MiniMax base URL
                MockOpenAI.assert_called_once()
                call_kwargs = MockOpenAI.call_args[1]
                assert call_kwargs["api_key"] == "test-minimax-key"
                assert call_kwargs["base_url"] == "https://api.minimax.io/v1"

    def test_model_spec_accessible(self, minimax_model_spec, mock_tokenizer):
        """Should expose model_spec property."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                MockOpenAI.return_value = MagicMock()

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                assert provider.model_spec.api_model_name == "MiniMax-M2.7"
                assert provider.model_spec.context_window == 1_000_000


# ── Structured output tests ───────────────────────────────────────────


class TestMiniMaxLLMStructuredOutput:
    """Tests for MiniMaxLLM structured output."""

    @pytest.mark.asyncio
    async def test_structured_output_returns_parsed_model(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should parse valid JSON response into Pydantic model."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content='{"name": "test", "score": 42}'))
                ]
                mock_response.usage = MagicMock(
                    prompt_tokens=50, completion_tokens=20, total_tokens=70
                )
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                result = await provider.structured_output(
                    prompt="Generate test data",
                    schema=TestSchema,
                    system_prompt="You are a test assistant.",
                )

                assert isinstance(result, TestSchema)
                assert result.name == "test"
                assert result.score == 42

    @pytest.mark.asyncio
    async def test_structured_output_uses_json_object_format(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should use json_object response format (not strict json_schema)."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content='{"name": "x", "score": 1}'))
                ]
                mock_response.usage = MagicMock(
                    prompt_tokens=50, completion_tokens=20, total_tokens=70
                )
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                await provider.structured_output(
                    prompt="Test",
                    schema=TestSchema,
                    system_prompt="System prompt.",
                )

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs["response_format"] == {"type": "json_object"}
                assert call_kwargs["model"] == "MiniMax-M2.7"
                assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_structured_output_includes_schema_in_system_prompt(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should embed JSON schema instructions in the system prompt."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content='{"name": "x", "score": 1}'))
                ]
                mock_response.usage = None
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                await provider.structured_output(
                    prompt="Test",
                    schema=TestSchema,
                    system_prompt="Base system prompt.",
                )

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                system_msg = call_kwargs["messages"][0]["content"]
                assert "Base system prompt." in system_msg
                assert "JSON" in system_msg
                assert "schema" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_structured_output_strips_think_tags(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should strip <think>...</think> blocks from M2.7 responses."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                content_with_think = (
                    '<think>Let me think about this...</think>'
                    '{"name": "thought_result", "score": 99}'
                )
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content=content_with_think))
                ]
                mock_response.usage = None
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                result = await provider.structured_output(
                    prompt="Test",
                    schema=TestSchema,
                    system_prompt="System.",
                )

                assert result.name == "thought_result"
                assert result.score == 99

    @pytest.mark.asyncio
    async def test_structured_output_raises_on_empty_response(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should raise TimeoutError on empty response content."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content=None))]
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(
                    model_spec=minimax_model_spec,
                    tokenizer=mock_tokenizer,
                    max_retries=0,
                )

                with pytest.raises(TimeoutError, match="empty response"):
                    await provider.structured_output(
                        prompt="Test",
                        schema=TestSchema,
                        system_prompt="System.",
                    )

    @pytest.mark.asyncio
    async def test_structured_output_raises_on_invalid_json(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should raise RuntimeError on invalid JSON response."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="not valid json"))
                ]
                mock_response.usage = None
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(
                    model_spec=minimax_model_spec,
                    tokenizer=mock_tokenizer,
                    max_retries=0,
                )

                with pytest.raises(RuntimeError, match="invalid JSON"):
                    await provider.structured_output(
                        prompt="Test",
                        schema=TestSchema,
                        system_prompt="System.",
                    )

    @pytest.mark.asyncio
    async def test_structured_output_raises_on_empty_prompt(
        self, minimax_model_spec, mock_tokenizer
    ):
        """Should raise ValueError on empty prompt."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                MockOpenAI.return_value = AsyncMock()

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)

                with pytest.raises(ValueError, match="empty"):
                    await provider.structured_output(
                        prompt="",
                        schema=TestSchema,
                        system_prompt="System.",
                    )


# ── Think-tag stripping tests ─────────────────────────────────────────


class TestStripThinkTags:
    """Tests for _strip_think_tags static method."""

    def test_strips_single_think_block(self):
        from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

        result = MiniMaxLLM._strip_think_tags(
            "<think>reasoning here</think>actual content"
        )
        assert result == "actual content"

    def test_strips_multiline_think_block(self):
        from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

        result = MiniMaxLLM._strip_think_tags(
            "<think>\nline 1\nline 2\n</think>\n{}"
        )
        assert result == "{}"

    def test_preserves_text_without_think_tags(self):
        from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

        result = MiniMaxLLM._strip_think_tags('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_strips_multiple_think_blocks(self):
        from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

        result = MiniMaxLLM._strip_think_tags(
            "<think>a</think>middle<think>b</think>end"
        )
        assert result == "middleend"


# ── Close tests ────────────────────────────────────────────────────────


class TestMiniMaxLLMClose:
    """Tests for MiniMaxLLM.close()."""

    @pytest.mark.asyncio
    async def test_close_calls_client_close(self, minimax_model_spec, mock_tokenizer):
        """Should close the underlying OpenAI client."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                mock_client = AsyncMock()
                MockOpenAI.return_value = mock_client

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                provider = MiniMaxLLM(model_spec=minimax_model_spec, tokenizer=mock_tokenizer)
                await provider.close()

                mock_client.close.assert_called_once()


# ── Services integration tests ─────────────────────────────────────────


class TestMiniMaxInServices:
    """Tests for MiniMax provider creation in AgenticSearchServices."""

    def test_create_single_provider_minimax(self, minimax_model_spec, mock_tokenizer):
        """_create_single_provider should create MiniMaxLLM for MINIMAX provider."""
        with patch("airweave.search.agentic_search.external.llm.minimax.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch(
                "airweave.search.agentic_search.external.llm.minimax.AsyncOpenAI"
            ) as MockOpenAI:
                MockOpenAI.return_value = MagicMock()

                from airweave.search.agentic_search.services import AgenticSearchServices

                provider = AgenticSearchServices._create_single_provider(
                    LLMProvider.MINIMAX, minimax_model_spec, mock_tokenizer
                )

                from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM

                assert isinstance(provider, MiniMaxLLM)


# ── Integration test (requires MINIMAX_API_KEY) ───────────────────────


@pytest.mark.skipif(
    not __import__("os").environ.get("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set",
)
class TestMiniMaxLLMIntegration:
    """Integration tests that call the real MiniMax API."""

    @pytest.mark.asyncio
    async def test_real_structured_output(self):
        """Test structured output against real MiniMax API."""
        from airweave.search.agentic_search.external.llm.minimax import MiniMaxLLM
        from airweave.search.agentic_search.external.tokenizer.tiktoken import TiktokenTokenizer

        spec = get_model_spec(LLMProvider.MINIMAX, LLMModel.MINIMAX_M2_7)
        tokenizer = TiktokenTokenizer(model_spec=spec)

        provider = MiniMaxLLM(model_spec=spec, tokenizer=tokenizer)

        try:
            result = await provider.structured_output(
                prompt="Name a famous scientist and rate their impact 1-100.",
                schema=TestSchema,
                system_prompt="You are a helpful assistant.",
            )
            assert isinstance(result, TestSchema)
            assert len(result.name) > 0
            assert 1 <= result.score <= 100
        finally:
            await provider.close()
