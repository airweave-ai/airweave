"""Unit tests for DestinationHandler retry and timing behavior.

Verifies that:
1. TimeoutError flows through _execute_with_retry as a retryable exception
2. After max retries, SyncFailureError is raised (fail fast, fail loud)
3. Timing logs fire for slow operations (>10s)
4. Timing logs fire for slow content processing (>10s)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.destination import DestinationHandler


def _make_mock_destination(soft_fail=False):
    """Create a mock destination with required attributes."""
    dest = MagicMock()
    dest.__class__.__name__ = "MockDestination"
    dest.soft_fail = soft_fail
    dest.processing_requirement = MagicMock()
    dest.bulk_insert = AsyncMock()
    dest.bulk_delete_by_parent_ids = AsyncMock()
    return dest


def _make_mock_sync_context():
    """Create a mock sync context with logger."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.logger.warning = MagicMock()
    ctx.logger.error = MagicMock()
    ctx.logger.debug = MagicMock()
    ctx.sync = MagicMock()
    ctx.sync.id = "test-sync-id"
    return ctx


class TestExecuteWithRetryTimeout:
    """Test that TimeoutError is retried and eventually fails loud."""

    @pytest.mark.asyncio
    async def test_timeout_error_is_retried(self):
        """TimeoutError should be caught and retried up to max_retries times."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("feed timed out")

        with patch("airweave.platform.sync.handlers.destination.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SyncFailureError, match="Destination unavailable"):
                await handler._execute_with_retry(
                    operation=failing_operation,
                    operation_name="insert_MockDestination",
                    destination=dest,
                    sync_context=ctx,
                    max_retries=2,
                )

        # initial attempt + 2 retries = 3 total calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_asyncio_timeout_error_is_retried(self):
        """asyncio.TimeoutError (subclass of TimeoutError) should also be retried."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise asyncio.TimeoutError()

        with patch("airweave.platform.sync.handlers.destination.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SyncFailureError, match="Destination unavailable"):
                await handler._execute_with_retry(
                    operation=failing_operation,
                    operation_name="insert_MockDestination",
                    destination=dest,
                    sync_context=ctx,
                    max_retries=2,
                )

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_succeeds_on_retry(self):
        """If operation succeeds on retry, no error is raised."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("temporary failure")
            return "success"

        with patch("airweave.platform.sync.handlers.destination.asyncio.sleep", new_callable=AsyncMock):
            result = await handler._execute_with_retry(
                operation=flaky_operation,
                operation_name="insert_MockDestination",
                destination=dest,
                sync_context=ctx,
                max_retries=4,
            )

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_retry_logs_warning_on_each_failure(self):
        """Each retry should log a warning with attempt number."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        async def failing_operation():
            raise TimeoutError("feed timed out")

        with patch("airweave.platform.sync.handlers.destination.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SyncFailureError):
                await handler._execute_with_retry(
                    operation=failing_operation,
                    operation_name="insert_MockDestination",
                    destination=dest,
                    sync_context=ctx,
                    max_retries=2,
                )

        # Should have 2 warning logs (attempt 1 and 2, not the final failure)
        warning_calls = ctx.logger.warning.call_args_list
        retry_warnings = [c for c in warning_calls if "Retrying" in str(c)]
        assert len(retry_warnings) == 2

    @pytest.mark.asyncio
    async def test_non_retryable_exception_fails_immediately(self):
        """Non-retryable exceptions should fail immediately with SyncFailureError."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad data")

        with pytest.raises(SyncFailureError, match="Destination failed"):
            await handler._execute_with_retry(
                operation=failing_operation,
                operation_name="insert_MockDestination",
                destination=dest,
                sync_context=ctx,
                max_retries=4,
            )

        # Should NOT retry - fails on first attempt
        assert call_count == 1


class TestTimingLogs:
    """Test that timing logs fire for slow operations."""

    @pytest.mark.asyncio
    async def test_slow_operation_logs_warning(self):
        """Operations taking >10s should log a warning."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        # Mock the event loop time to simulate a 15-second operation
        time_values = [0.0, 15.0]  # start, end
        time_iter = iter(time_values)

        async def slow_operation():
            return "done"

        mock_loop = MagicMock()
        mock_loop.time = MagicMock(side_effect=time_iter)

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await handler._execute_with_retry(
                operation=slow_operation,
                operation_name="insert_MockDestination",
                destination=dest,
                sync_context=ctx,
            )

        # Should log warning about slow operation
        warning_calls = ctx.logger.warning.call_args_list
        slow_warnings = [c for c in warning_calls if "slow" in str(c)]
        assert len(slow_warnings) == 1
        assert "15.0s" in str(slow_warnings[0])

    @pytest.mark.asyncio
    async def test_fast_operation_does_not_log_warning(self):
        """Operations completing in <10s should not log a warning."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        # Mock the event loop time to simulate a 0.5-second operation
        time_values = [0.0, 0.5]
        time_iter = iter(time_values)

        async def fast_operation():
            return "done"

        mock_loop = MagicMock()
        mock_loop.time = MagicMock(side_effect=time_iter)

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            await handler._execute_with_retry(
                operation=fast_operation,
                operation_name="insert_MockDestination",
                destination=dest,
                sync_context=ctx,
            )

        # Should NOT log warning
        warning_calls = ctx.logger.warning.call_args_list
        slow_warnings = [c for c in warning_calls if "slow" in str(c)]
        assert len(slow_warnings) == 0

    @pytest.mark.asyncio
    async def test_slow_processing_logs_warning(self):
        """Content processing (chunking/embedding) taking >10s should log a warning."""
        dest = _make_mock_destination()
        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        # Mock processor
        mock_processor = MagicMock()
        mock_processor.__class__.__name__ = "ChunkEmbedProcessor"
        mock_processor.process = AsyncMock(return_value=[])

        # Mock the event loop time to simulate 15s processing
        time_values = [0.0, 15.0]
        time_iter = iter(time_values)

        mock_loop = MagicMock()
        mock_loop.time = MagicMock(side_effect=time_iter)

        # Mock entity with model_copy
        mock_entity = MagicMock()
        mock_entity.model_copy = MagicMock(return_value=mock_entity)

        mock_runtime = MagicMock()

        with patch("asyncio.get_running_loop", return_value=mock_loop), \
             patch.object(handler, "_get_processor", return_value=mock_processor):
            await handler._do_process_and_insert([mock_entity], ctx, mock_runtime)

        # Should log warning about slow processing
        warning_calls = ctx.logger.warning.call_args_list
        slow_warnings = [c for c in warning_calls if "slow" in str(c)]
        assert len(slow_warnings) == 1
        assert "ChunkEmbedProcessor" in str(slow_warnings[0])
        assert "15.0s" in str(slow_warnings[0])
