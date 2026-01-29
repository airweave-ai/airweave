"""Unit tests for MistralProvider (search provider)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_model_spec():
    """Create mock ProviderModelSpec for Mistral."""
    from airweave.search.providers.schemas import (
        EmbeddingModelConfig,
        LLMModelConfig,
        ProviderModelSpec,
        RerankModelConfig,
    )

    return ProviderModelSpec(
        embedding_model=EmbeddingModelConfig(
            name="mistral-embed",
            tokenizer="mistral-embed",
            dimensions=1024,
            max_tokens=8192,
        ),
        llm_model=LLMModelConfig(
            name="mistral-small-latest",
            tokenizer="mistral-small-latest",
            context_window=32000,
        ),
        rerank_model=RerankModelConfig(
            name="mistral-small-latest",
            tokenizer="mistral-small-latest",
            context_window=32000,
        ),
    )


@pytest.fixture
def mock_ctx():
    """Create mock ApiContext."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.logger.info = MagicMock()
    ctx.logger.debug = MagicMock()
    ctx.logger.warning = MagicMock()
    return ctx


class TestMistralProviderInit:
    """Tests for MistralProvider initialization."""

    def test_initializes_with_valid_config(self, mock_model_spec, mock_ctx):
        """Test provider initializes successfully with valid config."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            assert provider is not None
            MockMistral.assert_called_once_with(api_key="test-api-key")

    def test_initializes_tokenizers(self, mock_model_spec, mock_ctx):
        """Test that tokenizers are initialized."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            # Should have initialized tokenizers
            assert provider.llm_tokenizer is not None
            assert provider.embedding_tokenizer is not None

    def test_mock_mode_without_client(self, mock_ctx):
        """Test mock mode doesn't require Mistral client."""
        from airweave.search.providers.schemas import (
            EmbeddingModelConfig,
            ProviderModelSpec,
        )

        mock_spec = ProviderModelSpec(
            embedding_model=EmbeddingModelConfig(
                name="mock-mistral-embed",
                tokenizer="cl100k_base",
                dimensions=1024,
                max_tokens=8192,
            ),
            llm_model=None,
            rerank_model=None,
        )

        from airweave.search.providers import MistralProvider

        # Should not raise even without real Mistral client
        provider = MistralProvider(
            api_key="test-api-key",
            model_spec=mock_spec,
            ctx=mock_ctx,
        )

        assert provider._mock_embeddings is True


class TestMistralProviderEmbed:
    """Tests for MistralProvider.embed()."""

    @pytest.mark.asyncio
    async def test_embed_validates_dimensions(self, mock_model_spec, mock_ctx):
        """Test embed rejects non-1024 dimensions."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider
            from airweave.search.providers._base import ProviderError

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            # Should raise when requesting non-1024 dimensions
            with pytest.raises(ProviderError) as exc_info:
                await provider.embed(["test text"], dimensions=1536)

            assert "1024 dimensions" in str(exc_info.value)
            assert "1536" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_accepts_matching_dimensions(self, mock_model_spec, mock_ctx):
        """Test embed accepts matching dimensions."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1024)]
            mock_client.embeddings.create_async = AsyncMock(return_value=mock_response)
            MockMistral.return_value = mock_client

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            # Should not raise when requesting 1024 dimensions
            result = await provider.embed(["test text"], dimensions=1024)

            assert len(result) == 1
            assert len(result[0]) == 1024

    @pytest.mark.asyncio
    async def test_embed_raises_on_empty_input(self, mock_model_spec, mock_ctx):
        """Test embed raises on empty text list."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(ValueError) as exc_info:
                await provider.embed([])

            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_raises_on_empty_text(self, mock_model_spec, mock_ctx):
        """Test embed raises when text is empty string."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(ValueError) as exc_info:
                await provider.embed([""])

            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mock_embed_returns_deterministic_vectors(self, mock_ctx):
        """Test mock embeddings are deterministic."""
        from airweave.search.providers.schemas import (
            EmbeddingModelConfig,
            ProviderModelSpec,
        )

        mock_spec = ProviderModelSpec(
            embedding_model=EmbeddingModelConfig(
                name="mock-mistral-embed",
                tokenizer="cl100k_base",
                dimensions=1024,
                max_tokens=8192,
            ),
            llm_model=None,
            rerank_model=None,
        )

        from airweave.search.providers import MistralProvider

        provider = MistralProvider(
            api_key="test-api-key",
            model_spec=mock_spec,
            ctx=mock_ctx,
        )

        # Same text should produce same embedding
        result1 = await provider.embed(["test text"])
        result2 = await provider.embed(["test text"])

        assert result1 == result2


class TestMistralProviderGenerate:
    """Tests for MistralProvider.generate()."""

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, mock_model_spec, mock_ctx):
        """Test generate returns completion text."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Generated text"))]
            mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
            MockMistral.return_value = mock_client

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            result = await provider.generate([{"role": "user", "content": "Hello"}])

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_generate_raises_on_empty_messages(self, mock_model_spec, mock_ctx):
        """Test generate raises on empty messages."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(ValueError) as exc_info:
                await provider.generate([])

            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_raises_when_no_llm_model(self, mock_ctx):
        """Test generate raises when LLM model not configured."""
        from airweave.search.providers.schemas import (
            EmbeddingModelConfig,
            ProviderModelSpec,
        )

        # Model spec without LLM
        mock_spec = ProviderModelSpec(
            embedding_model=EmbeddingModelConfig(
                name="mistral-embed",
                tokenizer="mistral-embed",
                dimensions=1024,
                max_tokens=8192,
            ),
            llm_model=None,
            rerank_model=None,
        )

        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(RuntimeError) as exc_info:
                await provider.generate([{"role": "user", "content": "Hello"}])

            assert "not configured" in str(exc_info.value).lower()


class TestMistralProviderStructuredOutput:
    """Tests for MistralProvider.structured_output()."""

    @pytest.mark.asyncio
    async def test_structured_output_returns_parsed_model(self, mock_model_spec, mock_ctx):
        """Test structured_output returns parsed Pydantic model."""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            name: str
            value: int

        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content='{"name": "test", "value": 42}'))
            ]
            mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
            MockMistral.return_value = mock_client

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            result = await provider.structured_output(
                [{"role": "user", "content": "Generate test data"}],
                schema=TestSchema,
            )

            assert isinstance(result, TestSchema)
            assert result.name == "test"
            assert result.value == 42


class TestMistralProviderRerank:
    """Tests for MistralProvider.rerank()."""

    @pytest.mark.asyncio
    async def test_rerank_raises_on_empty_documents(self, mock_model_spec, mock_ctx):
        """Test rerank raises on empty document list."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(ValueError) as exc_info:
                await provider.rerank("query", [], top_n=5)

            assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rerank_raises_on_invalid_top_n(self, mock_model_spec, mock_ctx):
        """Test rerank raises on invalid top_n."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(ValueError) as exc_info:
                await provider.rerank("query", ["doc1"], top_n=0)

            assert "top_n" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rerank_raises_when_no_rerank_model(self, mock_ctx):
        """Test rerank raises when rerank model not configured."""
        from airweave.search.providers.schemas import (
            EmbeddingModelConfig,
            ProviderModelSpec,
        )

        # Model spec without rerank
        mock_spec = ProviderModelSpec(
            embedding_model=EmbeddingModelConfig(
                name="mistral-embed",
                tokenizer="mistral-embed",
                dimensions=1024,
                max_tokens=8192,
            ),
            llm_model=None,
            rerank_model=None,
        )

        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_spec,
                ctx=mock_ctx,
            )

            with pytest.raises(RuntimeError) as exc_info:
                await provider.rerank("query", ["doc1", "doc2"], top_n=1)

            assert "not configured" in str(exc_info.value).lower()


class TestMistralProviderTokenCounting:
    """Tests for token counting in MistralProvider."""

    def test_count_tokens_uses_tokenizer(self, mock_model_spec, mock_ctx):
        """Test count_tokens uses the configured tokenizer."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            # Should be able to count tokens
            count = provider.count_tokens("Hello, world!", provider.llm_tokenizer)

            assert isinstance(count, int)
            assert count > 0

    def test_count_tokens_returns_zero_for_none(self, mock_model_spec, mock_ctx):
        """Test count_tokens returns 0 for None text."""
        with patch("airweave.search.providers.mistral.Mistral") as MockMistral:
            MockMistral.return_value = MagicMock()

            from airweave.search.providers import MistralProvider

            provider = MistralProvider(
                api_key="test-api-key",
                model_spec=mock_model_spec,
                ctx=mock_ctx,
            )

            count = provider.count_tokens(None, provider.llm_tokenizer)

            assert count == 0
