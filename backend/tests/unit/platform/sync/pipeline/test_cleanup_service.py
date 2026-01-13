"""Tests for CleanupService progressive temp file cleanup.

Validates that temporary files are cleaned up correctly for different action types:
- INSERT: Files that are new
- UPDATE: Files that changed
- KEEP: Files that are unchanged (bug fix: these were being skipped)
- DELETE: Deletion signals (should be ignored - no files downloaded)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, FileEntity
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.pipeline.cleanup_service import cleanup_service


# Test entity classes
class _TestFileEntity(FileEntity):
    """Test FileEntity for cleanup validation."""

    file_id: str = AirweaveField(..., description="Test file ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Test file name", is_name=True)
    url: str = AirweaveField(default="https://example.com/test.txt", description="Test URL")
    size: int = AirweaveField(default=1024, description="Test file size")
    file_type: str = AirweaveField(default="text/plain", description="Test file type")


class _TestNonFileEntity(BaseEntity):
    """Test non-file entity (should be ignored in cleanup)."""

    test_id: str = AirweaveField(..., description="Test ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Test name", is_name=True)


class _TestDeletionEntity(DeletionEntity):
    """Test DeletionEntity (should be ignored in cleanup)."""

    deletion_id: str = AirweaveField(..., description="Deletion ID", is_entity_id=True)
    label: str = AirweaveField(..., description="Deletion label", is_name=True)
    deletion_status: str = "removed"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_sync_context():
    """Create a mock SyncContext."""
    context = MagicMock()
    context.logger = MagicMock()
    context.logger.debug = MagicMock()
    context.logger.error = MagicMock()
    return context


def create_file_entity_with_temp_file(temp_dir: str, filename: str) -> _TestFileEntity:
    """Create a FileEntity with an actual temp file on disk."""
    file_path = os.path.join(temp_dir, filename)
    Path(file_path).write_text("test content")
    
    entity = _TestFileEntity(
        file_id=str(uuid4()),
        name=filename,
        url=f"https://example.com/{filename}",
        breadcrumbs=[]
    )
    entity.local_path = file_path
    return entity


@pytest.mark.asyncio
async def test_cleanup_inserts(temp_dir, mock_sync_context):
    """Test that INSERT action files are cleaned up."""
    # Create file entity with temp file
    entity = create_file_entity_with_temp_file(temp_dir, "insert.txt")
    
    partitions = {
        "inserts": [entity],
        "updates": [],
        "keeps": [],
        "deletes": [],
    }
    
    # Verify file exists before cleanup
    assert os.path.exists(entity.local_path)
    
    # Run cleanup
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    
    # Verify file was deleted
    assert not os.path.exists(entity.local_path)
    mock_sync_context.logger.debug.assert_called()


@pytest.mark.asyncio
async def test_cleanup_updates(temp_dir, mock_sync_context):
    """Test that UPDATE action files are cleaned up."""
    entity = create_file_entity_with_temp_file(temp_dir, "update.txt")
    
    partitions = {
        "inserts": [],
        "updates": [entity],
        "keeps": [],
        "deletes": [],
    }
    
    assert os.path.exists(entity.local_path)
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    assert not os.path.exists(entity.local_path)


@pytest.mark.asyncio
async def test_cleanup_keeps(temp_dir, mock_sync_context):
    """Test that KEEP action files are cleaned up.
    
    This is the critical bug fix - KEEP files (unchanged) were being downloaded
    and hashed but never cleaned up, causing disk buildup.
    """
    entity = create_file_entity_with_temp_file(temp_dir, "keep.txt")
    
    partitions = {
        "inserts": [],
        "updates": [],
        "keeps": [entity],
        "deletes": [],
    }
    
    assert os.path.exists(entity.local_path)
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    assert not os.path.exists(entity.local_path), "KEEP files should be cleaned up!"


@pytest.mark.asyncio
async def test_cleanup_mixed_actions(temp_dir, mock_sync_context):
    """Test that all file action types (INSERT, UPDATE, KEEP) are cleaned up."""
    insert_entity = create_file_entity_with_temp_file(temp_dir, "insert.txt")
    update_entity = create_file_entity_with_temp_file(temp_dir, "update.txt")
    keep_entity = create_file_entity_with_temp_file(temp_dir, "keep.txt")
    
    partitions = {
        "inserts": [insert_entity],
        "updates": [update_entity],
        "keeps": [keep_entity],
        "deletes": [],
    }
    
    # All files exist
    assert os.path.exists(insert_entity.local_path)
    assert os.path.exists(update_entity.local_path)
    assert os.path.exists(keep_entity.local_path)
    
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    
    # All files deleted
    assert not os.path.exists(insert_entity.local_path)
    assert not os.path.exists(update_entity.local_path)
    assert not os.path.exists(keep_entity.local_path)


@pytest.mark.asyncio
async def test_cleanup_ignores_deletes(temp_dir, mock_sync_context):
    """Test that DELETE actions are ignored (no files to clean).
    
    DeletionEntity is not a FileEntity, so it should be skipped.
    """
    # Create a deletion entity (no file on disk)
    deletion_entity = _TestDeletionEntity(deletion_id=str(uuid4()), label="deleted-item", breadcrumbs=[])
    
    partitions = {
        "inserts": [],
        "updates": [],
        "keeps": [],
        "deletes": [deletion_entity],
    }
    
    # Should not raise any errors
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    
    # No cleanup logged since no FileEntities
    assert not any(
        "Progressive cleanup: deleted" in str(call)
        for call in mock_sync_context.logger.debug.call_args_list
    )


@pytest.mark.asyncio
async def test_cleanup_ignores_non_file_entities(temp_dir, mock_sync_context):
    """Test that non-FileEntity types are ignored."""
    # Mix FileEntity with non-FileEntity
    file_entity = create_file_entity_with_temp_file(temp_dir, "file.txt")
    non_file_entity = _TestNonFileEntity(test_id=str(uuid4()), name="non-file-entity", breadcrumbs=[])
    
    partitions = {
        "inserts": [file_entity, non_file_entity],
        "updates": [],
        "keeps": [],
        "deletes": [],
    }
    
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
    
    # Only FileEntity was cleaned
    assert not os.path.exists(file_entity.local_path)


@pytest.mark.asyncio
async def test_cleanup_raises_on_failed_deletion(temp_dir, mock_sync_context):
    """Test that cleanup raises SyncFailureError if file deletion fails."""
    entity = create_file_entity_with_temp_file(temp_dir, "locked.txt")
    
    partitions = {
        "inserts": [entity],
        "updates": [],
        "keeps": [],
        "deletes": [],
    }
    
    # Mock os.remove to fail
    original_remove = os.remove
    
    def mock_remove(path):
        if "locked.txt" in path:
            # Simulate file still exists after removal attempt
            return
        original_remove(path)
    
    with pytest.raises(SyncFailureError, match="Failed to delete .* temp files"):
        with patch("os.remove", side_effect=mock_remove):
            await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)


@pytest.mark.asyncio
async def test_cleanup_raises_on_missing_local_path(mock_sync_context):
    """Test that FileEntity without local_path raises error."""
    entity = _TestFileEntity(file_id=str(uuid4()), name="no-path.txt", breadcrumbs=[])
    # No local_path set - programming error
    
    partitions = {
        "inserts": [entity],
        "updates": [],
        "keeps": [],
        "deletes": [],
    }
    
    with pytest.raises(SyncFailureError, match="has no local_path after processing"):
        await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)


@pytest.mark.asyncio
async def test_cleanup_handles_already_deleted_files(temp_dir, mock_sync_context):
    """Test that cleanup handles files that were already deleted gracefully."""
    entity = create_file_entity_with_temp_file(temp_dir, "already_deleted.txt")
    
    # Delete the file manually before cleanup
    os.remove(entity.local_path)
    
    partitions = {
        "inserts": [entity],
        "updates": [],
        "keeps": [],
        "deletes": [],
    }
    
    # Should not raise error
    await cleanup_service.cleanup_processed_files(partitions, mock_sync_context)
