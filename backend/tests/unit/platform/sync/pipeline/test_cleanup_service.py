"""Unit tests for CleanupService temp file cleanup."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from airweave.platform.sync.pipeline.cleanup_service import CleanupService
from airweave.platform.contexts import SyncContext, SourceContext


class MockSource:
    """Mock source with file_downloader."""
    
    def __init__(self, has_downloader=True):
        if has_downloader:
            self.file_downloader = Mock()
            self.file_downloader.cleanup_sync_directory = AsyncMock()


class TestCleanupService:
    """Test suite for CleanupService."""

    @pytest.mark.asyncio
    async def test_cleanup_checks_source_instance_not_wrapper(self):
        """Verify cleanup checks source_instance, not the SourceContext wrapper.
        
        Regression test for bug where hasattr checked sync_context.source (SourceContext)
        instead of sync_context.source_instance (actual BaseSource), causing all
        temp file cleanups to be skipped.
        """
        # Create mock source WITH file_downloader
        mock_source = MockSource(has_downloader=True)
        
        # Create SourceContext (wrapper) - does NOT have file_downloader attribute
        source_context = Mock(spec=SourceContext)
        source_context.source = mock_source  # The actual source instance
        
        # Create SyncContext
        sync_context = Mock(spec=SyncContext)
        sync_context.source = source_context  # This is the wrapper
        sync_context.source_instance = mock_source  # This is the actual source
        sync_context.logger = Mock()
        
        # Verify wrapper does NOT have file_downloader (this is the bug condition)
        assert not hasattr(source_context, "file_downloader"), \
            "SourceContext should not have file_downloader attribute"
        
        # Verify actual source DOES have file_downloader
        assert hasattr(mock_source, "file_downloader"), \
            "MockSource should have file_downloader attribute"
        
        # Run cleanup
        cleanup_service = CleanupService()
        await cleanup_service.cleanup_temp_files(sync_context)
        
        # Verify cleanup was called (proves we checked the right object)
        mock_source.file_downloader.cleanup_sync_directory.assert_called_once_with(
            sync_context.logger
        )

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_no_downloader(self):
        """Verify cleanup is skipped for sources without file_downloader."""
        # Create mock source WITHOUT file_downloader
        mock_source = Mock(spec=[])  # Empty spec = no attributes
        
        source_context = Mock(spec=SourceContext)
        source_context.source = mock_source
        
        sync_context = Mock(spec=SyncContext)
        sync_context.source = source_context
        sync_context.source_instance = mock_source
        sync_context.logger = Mock()
        
        # Verify source does NOT have file_downloader
        assert not hasattr(mock_source, "file_downloader")
        
        # Run cleanup - should skip without error
        cleanup_service = CleanupService()
        await cleanup_service.cleanup_temp_files(sync_context)
        
        # Verify debug log was called
        sync_context.logger.debug.assert_called_once()
        assert "API-only source" in sync_context.logger.debug.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_downloader_none(self):
        """Verify cleanup is skipped when file_downloader is None."""
        # Create mock source with file_downloader = None
        mock_source = Mock()
        mock_source.file_downloader = None
        
        source_context = Mock(spec=SourceContext)
        source_context.source = mock_source
        
        sync_context = Mock(spec=SyncContext)
        sync_context.source = source_context
        sync_context.source_instance = mock_source
        sync_context.logger = Mock()
        
        # Run cleanup - should skip
        cleanup_service = CleanupService()
        await cleanup_service.cleanup_temp_files(sync_context)
        
        # Verify debug log was called
        sync_context.logger.debug.assert_called_once()
        assert "not initialized" in sync_context.logger.debug.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cleanup_handles_exceptions_gracefully(self):
        """Verify cleanup errors are logged but don't raise."""
        # Create mock source that raises on cleanup
        mock_source = MockSource(has_downloader=True)
        mock_source.file_downloader.cleanup_sync_directory.side_effect = Exception("Disk error")
        
        source_context = Mock(spec=SourceContext)
        source_context.source = mock_source
        
        sync_context = Mock(spec=SyncContext)
        sync_context.source = source_context
        sync_context.source_instance = mock_source
        sync_context.logger = Mock()
        
        # Run cleanup - should not raise
        cleanup_service = CleanupService()
        await cleanup_service.cleanup_temp_files(sync_context)
        
        # Verify warning was logged
        sync_context.logger.warning.assert_called_once()
        assert "cleanup failed" in sync_context.logger.warning.call_args[0][0].lower()

