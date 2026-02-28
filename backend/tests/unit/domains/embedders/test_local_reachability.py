"""Tests for local embedder reachability check at startup."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from airweave.domains.embedders.config import (
    EmbeddingConfigError,
    _validate_local_reachability,
)
from airweave.domains.embedders.dense.local import LocalDenseEmbedder
from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder
from airweave.domains.embedders.types import DenseEmbedderEntry


def _make_entry(embedder_class: type, **overrides) -> DenseEmbedderEntry:
    """Build a minimal DenseEmbedderEntry for testing."""
    defaults = dict(
        short_name="test",
        name="Test",
        description="test entry",
        class_name=embedder_class.__name__,
        provider="local",
        api_model_name="test-model",
        max_dimensions=384,
        max_tokens=512,
        supports_matryoshka=False,
        embedder_class_ref=embedder_class,
        required_setting="TEXT2VEC_INFERENCE_URL",
    )
    defaults.update(overrides)
    return DenseEmbedderEntry(**defaults)


def _mock_client(get_return=None, get_side_effect=None):
    """Create a mock httpx.Client context manager."""
    client = MagicMock()
    if get_side_effect:
        client.get.side_effect = get_side_effect
    else:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        client.get.return_value = get_return or resp
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestValidateLocalReachability:
    """Tests for _validate_local_reachability."""

    def test_skips_non_local_embedder(self):
        """Non-local embedders are skipped without any HTTP call."""
        entry = _make_entry(
            OpenAIDenseEmbedder,
            provider="openai",
            required_setting="OPENAI_API_KEY",
        )
        _validate_local_reachability(entry)

    @patch("airweave.domains.embedders.config.settings")
    @patch("airweave.domains.embedders.config.httpx")
    def test_passes_when_service_reachable(self, mock_httpx, mock_settings):
        """Passes when the health endpoint returns 200."""
        mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"
        mock_httpx.Timeout = httpx.Timeout
        client = _mock_client()
        mock_httpx.Client.return_value = client

        entry = _make_entry(LocalDenseEmbedder)
        _validate_local_reachability(entry)

        client.get.assert_called_once_with("http://localhost:9878/health")

    @patch("airweave.domains.embedders.config.settings")
    @patch("airweave.domains.embedders.config.httpx")
    def test_raises_on_connection_error(self, mock_httpx, mock_settings):
        """Raises EmbeddingConfigError with actionable message on connection failure."""
        mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"
        mock_httpx.Timeout = httpx.Timeout
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.Client.return_value = _mock_client(
            get_side_effect=httpx.ConnectError("Connection refused")
        )

        entry = _make_entry(LocalDenseEmbedder)
        with pytest.raises(EmbeddingConfigError, match="not reachable"):
            _validate_local_reachability(entry)

    @patch("airweave.domains.embedders.config.settings")
    @patch("airweave.domains.embedders.config.httpx")
    def test_raises_on_timeout(self, mock_httpx, mock_settings):
        """Raises EmbeddingConfigError on timeout."""
        mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"
        mock_httpx.Timeout = httpx.Timeout
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.Client.return_value = _mock_client(
            get_side_effect=httpx.TimeoutException("timed out")
        )

        entry = _make_entry(LocalDenseEmbedder)
        with pytest.raises(EmbeddingConfigError, match="--profile local-embeddings"):
            _validate_local_reachability(entry)
