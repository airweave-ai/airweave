"""Tests for cursor loading with skip_cursor_load flag."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.sync.config import SyncExecutionConfig
from airweave.platform.sync.factory._context import ContextBuilder


class TestCursorLoadingWithExecutionConfig:
    """Test cursor loading respects skip_cursor_load flag."""

    @pytest.mark.asyncio
    async def test_skip_cursor_load_true_skips_loading(self):
        """Test that skip_cursor_load=True prevents cursor data from being loaded."""
        # Setup
        sync_id = uuid4()
        mock_sync = MagicMock(id=sync_id)
        source_connection_data = {
            "source_class": MagicMock(_cursor_class=None),
        }
        
        # Execution config with skip_cursor_load
        execution_config = SyncExecutionConfig(skip_cursor_load=True)
        
        # Mock database and context
        mock_db = AsyncMock()
        mock_ctx = MagicMock()
        mock_logger = MagicMock()
        
        builder = ContextBuilder(db=mock_db, ctx=mock_ctx, logger=mock_logger)
        
        # Mock sync_cursor_service to ensure it's NOT called
        with patch("airweave.platform.sync.factory._context.sync_cursor_service") as mock_service:
            mock_service.get_cursor_data = AsyncMock()
            
            cursor = await builder._create_cursor(
                sync=mock_sync,
                source_connection_data=source_connection_data,
                force_full_sync=False,
                execution_config=execution_config,
            )
            
            # Cursor data should be None (not loaded)
            assert cursor.cursor_data is None
            
            # Service should NOT have been called
            mock_service.get_cursor_data.assert_not_called()
            
            # Should log skip cursor load message
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("SKIP CURSOR LOAD" in call for call in log_calls)

    @pytest.mark.asyncio
    async def test_skip_cursor_load_false_loads_cursor(self):
        """Test that skip_cursor_load=False loads cursor data normally."""
        # Setup
        sync_id = uuid4()
        mock_sync = MagicMock(id=sync_id)
        source_connection_data = {
            "source_class": MagicMock(_cursor_class=None),
        }
        
        cursor_data = {"last_sync": "2024-01-01"}
        
        # Execution config WITHOUT skip_cursor_load
        execution_config = SyncExecutionConfig(skip_cursor_load=False)
        
        # Mock database and context
        mock_db = AsyncMock()
        mock_ctx = MagicMock()
        mock_logger = MagicMock()
        
        builder = ContextBuilder(db=mock_db, ctx=mock_ctx, logger=mock_logger)
        
        # Mock sync_cursor_service to return cursor data
        with patch("airweave.platform.sync.factory._context.sync_cursor_service") as mock_service:
            mock_service.get_cursor_data = AsyncMock(return_value=cursor_data)
            
            cursor = await builder._create_cursor(
                sync=mock_sync,
                source_connection_data=source_connection_data,
                force_full_sync=False,
                execution_config=execution_config,
            )
            
            # Cursor data should be loaded
            assert cursor.cursor_data == cursor_data
            
            # Service should have been called
            mock_service.get_cursor_data.assert_called_once()
            
            # Should log incremental sync message
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Incremental sync" in call for call in log_calls)

    @pytest.mark.asyncio
    async def test_force_full_sync_overrides_skip_cursor_load(self):
        """Test that force_full_sync=True takes precedence over skip_cursor_load."""
        # Setup
        sync_id = uuid4()
        mock_sync = MagicMock(id=sync_id)
        source_connection_data = {
            "source_class": MagicMock(_cursor_class=None),
        }
        
        # Execution config with skip_cursor_load, but force_full_sync should override
        execution_config = SyncExecutionConfig(skip_cursor_load=False)
        
        mock_db = AsyncMock()
        mock_ctx = MagicMock()
        mock_logger = MagicMock()
        
        builder = ContextBuilder(db=mock_db, ctx=mock_ctx, logger=mock_logger)
        
        with patch("airweave.platform.sync.factory._context.sync_cursor_service") as mock_service:
            mock_service.get_cursor_data = AsyncMock()
            
            cursor = await builder._create_cursor(
                sync=mock_sync,
                source_connection_data=source_connection_data,
                force_full_sync=True,  # This should override
                execution_config=execution_config,
            )
            
            # Cursor data should be None (not loaded)
            assert cursor.cursor_data is None
            
            # Service should NOT have been called
            mock_service.get_cursor_data.assert_not_called()
            
            # Should log FORCE FULL SYNC message (not skip cursor load)
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("FORCE FULL SYNC" in call for call in log_calls)

    @pytest.mark.asyncio
    async def test_no_execution_config_loads_cursor_normally(self):
        """Test that None execution_config behaves like default (loads cursor)."""
        # Setup
        sync_id = uuid4()
        mock_sync = MagicMock(id=sync_id)
        source_connection_data = {
            "source_class": MagicMock(_cursor_class=None),
        }
        
        cursor_data = {"last_sync": "2024-01-01"}
        
        mock_db = AsyncMock()
        mock_ctx = MagicMock()
        mock_logger = MagicMock()
        
        builder = ContextBuilder(db=mock_db, ctx=mock_ctx, logger=mock_logger)
        
        with patch("airweave.platform.sync.factory._context.sync_cursor_service") as mock_service:
            mock_service.get_cursor_data = AsyncMock(return_value=cursor_data)
            
            cursor = await builder._create_cursor(
                sync=mock_sync,
                source_connection_data=source_connection_data,
                force_full_sync=False,
                execution_config=None,  # No config
            )
            
            # Cursor data should be loaded
            assert cursor.cursor_data == cursor_data
            
            # Service should have been called
            mock_service.get_cursor_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_arf_capture_only_preset_skips_cursor(self):
        """Test that arf_capture_only preset properly skips cursor loading."""
        # Setup
        sync_id = uuid4()
        mock_sync = MagicMock(id=sync_id)
        source_connection_data = {
            "source_class": MagicMock(_cursor_class=None),
        }
        
        # Use the preset
        execution_config = SyncExecutionConfig.arf_capture_only()
        
        mock_db = AsyncMock()
        mock_ctx = MagicMock()
        mock_logger = MagicMock()
        
        builder = ContextBuilder(db=mock_db, ctx=mock_ctx, logger=mock_logger)
        
        with patch("airweave.platform.sync.factory._context.sync_cursor_service") as mock_service:
            mock_service.get_cursor_data = AsyncMock()
            
            cursor = await builder._create_cursor(
                sync=mock_sync,
                source_connection_data=source_connection_data,
                force_full_sync=False,
                execution_config=execution_config,
            )
            
            # Should NOT load cursor
            assert cursor.cursor_data is None
            mock_service.get_cursor_data.assert_not_called()

