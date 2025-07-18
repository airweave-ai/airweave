"""Tests for LocalText2Vec embedding model."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.embedding_models.local_text2vec import LocalText2Vec

@pytest.fixture
def model():
    # Adjust logger/context if needed for your environment
    return LocalText2Vec(logger=MagicMock())

class TestLocalText2Vec:
    """Tests for the LocalText2Vec embedding model."""

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
    @patch("httpx.AsyncClient.post")
    async def test_embed_success(self, mock_post, model):
        """Test successful embedding of a single text."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"vector": [0.1, 0.2, 0.3] * 128}
        mock_post.return_value = mock_response

        result = await model.embed("Test text")

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 384  # Default dimensions for this model

        # Verify the API call
        mock_post.assert_called_once_with(
            f"{model.inference_url}/vectors", json={"text": "Test text"}
        )

    @pytest.mark.asyncio
    async def test_embed_with_model_override(self, model):
        """Test that model override raises an error."""
        with pytest.raises(ValueError, match="Model override not supported"):
            await model.embed("Test text", model="other-model")

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
            "vectors": [[0.1, 0.2, 0.3] * 128, [0.4, 0.5, 0.6] * 128]
        }
        mock_post.return_value = mock_response

        texts = ["Text 1", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 384 for vec in result)

        # Verify the API call - updated to match the actual implementation
        # The method is making individual calls for each text rather than a batch call
        assert mock_post.call_count == 2
        mock_post.assert_any_call(f"{model.inference_url}/vectors/", json={"text": "Text 1"})
        mock_post.assert_any_call(f"{model.inference_url}/vectors/", json={"text": "Text 2"})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_embed_many_with_some_empty(self, mock_post, model):
        """Test embedding of a mix of empty and non-empty texts."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"vectors": [[0.1, 0.2, 0.3] * 128]}
        mock_post.return_value = mock_response

        texts = ["", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 384 for vec in result)
        assert all(v == 0.0 for v in result[0])  # First vector should be all zeros

        # Verify the API call
        mock_post.assert_called_once_with(
            f"{model.inference_url}/vectors/",
            json={"text": "Text 2"},  # Only non-empty text should be sent
        )

    @pytest.mark.asyncio
    async def test_embed_many_with_model_override(self, model):
        """Test that model override raises an error."""
        with pytest.raises(ValueError, match="Model override not supported"):
            await model.embed_many(["Test text"], model="other-model")

    @pytest.mark.asyncio
    async def test_embed_many_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed_many(["Test text"], dimensions=512)
