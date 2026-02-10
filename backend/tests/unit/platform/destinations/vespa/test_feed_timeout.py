"""Unit tests for Vespa feed timeout behavior.

Verifies that feed_documents raises asyncio.TimeoutError when the underlying
pyvespa feed_iterable takes longer than VESPA_TIMEOUT, preventing silent hangs
that block worker pool semaphore slots indefinitely.
"""

import asyncio
import time

import pytest
from unittest.mock import MagicMock, patch

from airweave.platform.destinations.vespa.client import VespaClient
from airweave.platform.destinations.vespa.types import VespaDocument


@pytest.fixture
def sample_docs():
    """Create sample VespaDocuments for feeding."""
    return {
        "base_entity": [
            VespaDocument(
                schema="base_entity",
                id="doc-1",
                fields={"entity_id": "1", "name": "Test"},
            ),
        ]
    }


class TestFeedTimeout:
    """Test that feed_documents respects VESPA_TIMEOUT."""

    @pytest.mark.asyncio
    async def test_feed_raises_timeout_when_feed_iterable_hangs(self, sample_docs):
        """When feed_iterable blocks longer than VESPA_TIMEOUT, asyncio.TimeoutError is raised."""
        mock_app = MagicMock()

        # Simulate a feed_iterable that blocks for 5 seconds (simulating a hang)
        def slow_feed_iterable(**kwargs):
            time.sleep(5)

        mock_app.feed_iterable = slow_feed_iterable
        client = VespaClient(app=mock_app)

        # Patch VESPA_TIMEOUT to 0.1s so the test completes quickly
        with patch("airweave.platform.destinations.vespa.client.settings") as mock_settings:
            mock_settings.VESPA_TIMEOUT = 0.1

            with pytest.raises(asyncio.TimeoutError):
                await client.feed_documents(sample_docs)

    @pytest.mark.asyncio
    async def test_feed_succeeds_within_timeout(self, sample_docs):
        """When feed_iterable completes within VESPA_TIMEOUT, no error is raised."""
        mock_app = MagicMock()

        # Simulate a fast feed
        def fast_feed_iterable(**kwargs):
            pass  # Returns immediately

        mock_app.feed_iterable = fast_feed_iterable
        client = VespaClient(app=mock_app)

        with patch("airweave.platform.destinations.vespa.client.settings") as mock_settings:
            mock_settings.VESPA_TIMEOUT = 5.0

            result = await client.feed_documents(sample_docs)
            assert result.success_count == 0  # No callback was invoked
            assert result.failed_docs == []

    @pytest.mark.asyncio
    async def test_feed_timeout_logs_error(self, sample_docs):
        """When timeout fires, an error is logged with schema name and doc count."""
        mock_app = MagicMock()

        def slow_feed_iterable(**kwargs):
            time.sleep(5)

        mock_app.feed_iterable = slow_feed_iterable

        mock_logger = MagicMock()
        client = VespaClient(app=mock_app, logger=mock_logger)

        with patch("airweave.platform.destinations.vespa.client.settings") as mock_settings:
            mock_settings.VESPA_TIMEOUT = 0.1

            with pytest.raises(asyncio.TimeoutError):
                await client.feed_documents(sample_docs)

            # Verify error was logged with schema name and doc count
            mock_logger.error.assert_called_once()
            log_msg = mock_logger.error.call_args[0][0]
            assert "TIMED OUT" in log_msg
            assert "base_entity" in log_msg
            assert "1 docs" in log_msg

    @pytest.mark.asyncio
    async def test_timeout_error_is_subclass_of_timeout_error(self):
        """Verify asyncio.TimeoutError is a subclass of TimeoutError.

        This is critical because _RETRYABLE_EXCEPTIONS in destination.py
        contains TimeoutError (not asyncio.TimeoutError). The retry logic
        depends on this inheritance relationship (true since Python 3.11).
        """
        assert issubclass(asyncio.TimeoutError, TimeoutError)
