"""Tests for OpenAIText2Vec embedding model."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec


class TestOpenAIText2Vec:
    """Tests for the OpenAIText2Vec embedding model."""

    @pytest.fixture
    def model_class(self):
        """Return the OpenAIText2Vec class."""
        return OpenAIText2Vec

    @pytest.fixture
    def model_kwargs(self):
        """Return kwargs for model initialization."""
        return {"api_key": "test-api-key", "embedding_model": "text-embedding-3-small"}

    @pytest.fixture
    def model(self, model_class, model_kwargs):
        """Create and return a model instance."""
        return model_class(**model_kwargs)

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, model):
        """Test embedding an empty string returns zero vector."""
        result = await model.embed("")
        assert isinstance(result, list)
        assert len(result) == model.vector_dimensions
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_many_empty_list(self, model):
        """Test embedding an empty list returns empty list."""
        result = await model.embed_many([])
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_embed_many_all_empty_strings(self, model):
        """Test embedding a list of empty strings returns zeros."""
        result = await model.embed_many(["", ""])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == model.vector_dimensions for vec in result)
        assert all(all(v == 0.0 for v in vec) for vec in result)

    @pytest.mark.asyncio
    async def test_create_classmethod(self, model_class, model_kwargs):
        """Test the create class method works."""
        model = model_class.create(**model_kwargs)
        assert isinstance(model, model_class)
        for key, value in model_kwargs.items():
            assert getattr(model, key) == value

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_success(self, mock_post, model):
        """Test successful embedding of a single text."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_post.return_value = mock_response

        result = await model.embed("Test text")

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 1536  # Default dimensions for OpenAI

        # Verify the API call
        mock_post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": "Test text",
                "model": "text-embedding-3-small",
                "encoding_format": "float",
            },
            timeout=60.0,
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_with_model_override(self, mock_post, model):
        """Test embedding with model override."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_post.return_value = mock_response

        _ = await model.embed("Test text", model="text-embedding-3-large")

        # Verify the API call uses the overridden model
        mock_post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": "Test text",
                "model": "text-embedding-3-large",
                "encoding_format": "float",
            },
            timeout=60.0,
        )

    @pytest.mark.asyncio
    async def test_embed_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed("Test text", dimensions=512)

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_many_success(self, mock_post, model):
        """Test successful embedding of multiple texts."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3] * 512}, {"embedding": [0.4, 0.5, 0.6] * 512}]
        }
        mock_post.return_value = mock_response

        texts = ["Text 1", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 1536 for vec in result)

        # Verify the API call
        mock_post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={"input": texts, "model": "text-embedding-3-small", "encoding_format": "float"},
            timeout=120.0,
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_many_with_some_empty(self, mock_post, model):
        """Test embedding of a mix of empty and non-empty texts."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_post.return_value = mock_response

        texts = ["", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 1536 for vec in result)
        assert all(v == 0.0 for v in result[0])  # First vector should be all zeros

        # Verify the API call only sends the non-empty text
        mock_post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": ["Text 2"],  # Only non-empty text
                "model": "text-embedding-3-small",
                "encoding_format": "float",
            },
            timeout=120.0,
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_many_with_model_override(self, mock_post, model):
        """Test embedding with model override."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_post.return_value = mock_response

        _ = await model.embed_many(["Test text"], model="text-embedding-3-large")

        # Verify the API call uses the overridden model
        mock_post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": ["Test text"],
                "model": "text-embedding-3-large",
                "encoding_format": "float",
            },
            timeout=120.0,
        )

    @pytest.mark.asyncio
    async def test_embed_many_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed_many(["Test text"], dimensions=512)
