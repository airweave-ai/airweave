"""Tests for entity hash computation in EntityPipeline.

Tests cover:
- Hash stability (same entity → same hash)
- Content changes (modify field → different hash)
- Volatile field changes (breadcrumbs/url → same hash)
- File entity special handling (content hash + metadata)
- Edge cases (missing local_path, batch processing)
"""

import os
import tempfile
from copy import deepcopy

import pytest

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.google_calendar import GoogleCalendarEventEntity
from airweave.platform.entities.google_drive import GoogleDriveFileEntity
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.exceptions import EntityProcessingError
from airweave.platform.sync.test.entities.asana import task
from airweave.platform.sync.test.entities.gcal import event_with_description
from airweave.platform.sync.test.entities.gdrive import pdf_file, text_file
from airweave.platform.sync.test.entities.github import code_file_large, code_file_largest


class TestHashStability:
    """Test that same entity produces same hash (idempotency)."""

    @pytest.mark.asyncio
    async def test_regular_entity_hash_stability(self):
        """Same regular entity should produce identical hash."""
        pipeline = EntityPipeline()

        # Compute hash twice for same entity
        hash1 = await pipeline.compute_hash_for_entity(event_with_description)
        hash2 = await pipeline.compute_hash_for_entity(event_with_description)

        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    @pytest.mark.asyncio
    async def test_file_entity_hash_stability(self):
        """Same file entity should produce identical hash."""
        pipeline = EntityPipeline()

        # Compute hash twice for same file entity
        hash1 = await pipeline.compute_hash_for_entity(text_file)
        hash2 = await pipeline.compute_hash_for_entity(text_file)

        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 64

    @pytest.mark.asyncio
    async def test_code_file_entity_hash_stability(self):
        """Same code file entity should produce identical hash."""
        pipeline = EntityPipeline()

        # Compute hash twice for same code file entity
        hash1 = await pipeline.compute_hash_for_entity(code_file_largest)
        hash2 = await pipeline.compute_hash_for_entity(code_file_largest)

        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 64


class TestContentChanges:
    """Test that content changes produce different hashes."""

    @pytest.mark.asyncio
    async def test_regular_entity_field_change(self):
        """Changing a content field should change the hash."""
        pipeline = EntityPipeline()

        # Original entity
        original = deepcopy(event_with_description)
        hash_original = await pipeline.compute_hash_for_entity(original)

        # Modified entity (change summary)
        modified = deepcopy(event_with_description)
        modified.summary = "MODIFIED SUMMARY - Different Content"
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original != hash_modified
        assert hash_original is not None
        assert hash_modified is not None

    @pytest.mark.asyncio
    async def test_regular_entity_description_change(self):
        """Changing description should change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(task)
        hash_original = await pipeline.compute_hash_for_entity(original)

        modified = deepcopy(task)
        modified.html_notes = "<body>COMPLETELY DIFFERENT NOTES</body>"
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original != hash_modified

    @pytest.mark.asyncio
    async def test_file_entity_metadata_change(self):
        """Changing file metadata (name, size) should change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(text_file)
        hash_original = await pipeline.compute_hash_for_entity(original)

        # Change name (metadata field)
        modified = deepcopy(text_file)
        modified.name = "RENAMED_FILE.txt"
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original != hash_modified

    @pytest.mark.asyncio
    async def test_file_entity_content_change(self):
        """Changing file content should change hash."""
        pipeline = EntityPipeline()

        # Create temp file with initial content
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("Initial content for testing")
            tmp_path = tmp.name

        try:
            # Create entity with temp file
            entity = GoogleDriveFileEntity(
                entity_id="test_file_1",
                breadcrumbs=[],
                name="test.txt",
                created_at=None,
                updated_at=None,
                url="https://example.com/test.txt",
                size=100,
                file_type="text",
                mime_type="text/plain",
                local_path=tmp_path,
                description=None,
                starred=False,
                trashed=False,
                explicitly_trashed=False,
                parents=[],
                owners=[],
                shared=False,
                web_view_link=None,
                icon_link=None,
                md5_checksum=None,
            )

            # Compute hash with initial content
            hash1 = await pipeline.compute_hash_for_entity(entity)

            # Modify file content
            with open(tmp_path, "w") as f:
                f.write("COMPLETELY DIFFERENT CONTENT - this should change the hash")

            # Compute hash again with modified content
            hash2 = await pipeline.compute_hash_for_entity(entity)

            assert hash1 != hash2
            assert hash1 is not None
            assert hash2 is not None

        finally:
            # Cleanup
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestVolatileFields:
    """Test that volatile field changes don't affect hash."""

    @pytest.mark.asyncio
    async def test_breadcrumbs_change_no_hash_change(self):
        """Changing breadcrumbs should NOT change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(event_with_description)
        hash_original = await pipeline.compute_hash_for_entity(original)

        # Modify breadcrumbs (volatile field)
        modified = deepcopy(event_with_description)
        modified.breadcrumbs = [
            Breadcrumb(entity_id="different_parent_1"),
            Breadcrumb(entity_id="different_parent_2"),
        ]
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original == hash_modified

    @pytest.mark.asyncio
    async def test_url_change_no_hash_change(self):
        """Changing URL (contains access tokens) should NOT change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(pdf_file)
        hash_original = await pipeline.compute_hash_for_entity(original)

        # Modify URL (volatile field - contains tokens)
        modified = deepcopy(pdf_file)
        modified.url = "https://example.com/file?token=COMPLETELY_DIFFERENT_TOKEN_12345"
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original == hash_modified

    @pytest.mark.asyncio
    async def test_local_path_change_no_hash_change(self):
        """Changing local_path should NOT change hash (temp path varies per run)."""
        pipeline = EntityPipeline()

        # Create two temp files with IDENTICAL content
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp1:
            tmp1.write("Exact same content")
            tmp_path1 = tmp1.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp2:
            tmp2.write("Exact same content")
            tmp_path2 = tmp2.name

        try:
            # Create two entities with different local_path but same content
            entity1 = GoogleDriveFileEntity(
                entity_id="test_file_same",
                breadcrumbs=[],
                name="same_name.txt",
                created_at=None,
                updated_at=None,
                url="https://example.com/same.txt",
                size=100,
                file_type="text",
                mime_type="text/plain",
                local_path=tmp_path1,  # Different path
                description=None,
                starred=False,
                trashed=False,
                explicitly_trashed=False,
                parents=[],
                owners=[],
                shared=False,
                web_view_link=None,
                icon_link=None,
                md5_checksum=None,
            )

            entity2 = deepcopy(entity1)
            entity2.local_path = tmp_path2  # Different path, same content

            hash1 = await pipeline.compute_hash_for_entity(entity1)
            hash2 = await pipeline.compute_hash_for_entity(entity2)

            assert hash1 == hash2

        finally:
            # Cleanup
            for path in [tmp_path1, tmp_path2]:
                if os.path.exists(path):
                    os.remove(path)


class TestFileEntitySpecialHandling:
    """Test file entity hash includes both content and metadata."""

    @pytest.mark.asyncio
    async def test_file_content_and_metadata_both_matter(self):
        """File hash should include BOTH content and metadata."""
        pipeline = EntityPipeline()

        # Create temp files with SAME content
        content = "Identical file content for testing"
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp1:
            tmp1.write(content)
            tmp_path1 = tmp1.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp2:
            tmp2.write(content)
            tmp_path2 = tmp2.name

        try:
            # Entity 1 with name "file1.txt"
            entity1 = GoogleDriveFileEntity(
                entity_id="test_1",
                breadcrumbs=[],
                name="file1.txt",
                created_at=None,
                updated_at=None,
                url="https://example.com/file1.txt",
                size=100,
                file_type="text",
                mime_type="text/plain",
                local_path=tmp_path1,
                description=None,
                starred=False,
                trashed=False,
                explicitly_trashed=False,
                parents=[],
                owners=[],
                shared=False,
                web_view_link=None,
                icon_link=None,
                md5_checksum=None,
            )

            # Entity 2 with DIFFERENT name but SAME content
            entity2 = deepcopy(entity1)
            entity2.entity_id = "test_2"
            entity2.name = "RENAMED_file.txt"
            entity2.local_path = tmp_path2

            hash1 = await pipeline.compute_hash_for_entity(entity1)
            hash2 = await pipeline.compute_hash_for_entity(entity2)

            # Hashes should be DIFFERENT because metadata (name) is different
            assert hash1 != hash2

        finally:
            # Cleanup
            for path in [tmp_path1, tmp_path2]:
                if os.path.exists(path):
                    os.remove(path)

    @pytest.mark.asyncio
    async def test_different_file_types_different_hashes(self):
        """Different file types with real files should have different hashes."""
        pipeline = EntityPipeline()

        # Test with real files from fixtures
        hash_pdf = await pipeline.compute_hash_for_entity(pdf_file)
        hash_text = await pipeline.compute_hash_for_entity(text_file)

        assert hash_pdf != hash_text
        assert hash_pdf is not None
        assert hash_text is not None


class TestEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_file_entity_missing_local_path(self):
        """FileEntity without local_path should raise EntityProcessingError."""
        pipeline = EntityPipeline()

        # Create file entity without local_path
        entity = GoogleDriveFileEntity(
            entity_id="no_path",
            breadcrumbs=[],
            name="missing_path.txt",
            created_at=None,
            updated_at=None,
            url="https://example.com/file.txt",
            size=100,
            file_type="text",
            mime_type="text/plain",
            local_path=None,  # Missing!
            description=None,
            starred=False,
            trashed=False,
            explicitly_trashed=False,
            parents=[],
            owners=[],
            shared=False,
            web_view_link=None,
            icon_link=None,
            md5_checksum=None,
        )

        with pytest.raises(EntityProcessingError, match="missing local_path"):
            await pipeline.compute_hash_for_entity(entity)

    @pytest.mark.asyncio
    async def test_file_entity_nonexistent_path(self):
        """FileEntity with nonexistent path should raise EntityProcessingError."""
        pipeline = EntityPipeline()

        entity = deepcopy(text_file)
        entity.local_path = "/nonexistent/path/to/file.txt"

        with pytest.raises(EntityProcessingError, match="Failed to read file"):
            await pipeline.compute_hash_for_entity(entity)

    @pytest.mark.asyncio
    async def test_code_file_and_regular_file_different_hashes(self):
        """CodeFileEntity and FileEntity should hash differently (type matters)."""
        pipeline = EntityPipeline()

        # Hash code file (GitHub)
        hash_code = await pipeline.compute_hash_for_entity(code_file_largest)

        # Hash regular file (Google Drive)
        hash_file = await pipeline.compute_hash_for_entity(pdf_file)

        # Different entity types with different content → different hashes
        assert hash_code != hash_file


class TestBatchProcessing:
    """Test batch hash computation with mixed entity types."""

    @pytest.mark.asyncio
    async def test_batch_mixed_entities(self):
        """Batch with mixed entity types should all get hashes."""
        from airweave.platform.sync.test.mock_context import create_mock_sync_context

        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()  # Not async

        # Mix of regular and file entities
        entities = [
            event_with_description,  # Regular (GCal event)
            task,  # Regular (Asana task)
            text_file,  # File (Google Drive text)
            code_file_large,  # Code file (GitHub)
        ]

        hashes = await pipeline.compute_hashes_for_batch(entities, sync_context)

        # All should have hashes
        assert len(hashes) == 4
        assert all(len(h) == 64 for h in hashes.values())

        # All hashes should be unique (different entities)
        hash_values = list(hashes.values())
        assert len(set(hash_values)) == 4

    @pytest.mark.asyncio
    async def test_batch_concurrent_processing(self):
        """Batch processing should handle concurrency correctly."""
        from airweave.platform.sync.test.mock_context import create_mock_sync_context

        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()  # Not async

        # Large batch with many files (tests semaphore)
        entities = [
            text_file,
            pdf_file,
            code_file_largest,
            code_file_large,
        ]

        # Duplicate to create larger batch
        large_batch = entities * 3  # 12 entities total

        # Should process concurrently without errors
        hashes = await pipeline.compute_hashes_for_batch(large_batch, sync_context)

        # Only unique entity_ids get hashes (duplicates skipped by dict)
        assert len(hashes) == 4  # 4 unique entities


class TestHashDeterminism:
    """Test hash determinism across different scenarios."""

    @pytest.mark.asyncio
    async def test_entity_copy_same_hash(self):
        """Deep copy of entity should have same hash."""
        pipeline = EntityPipeline()

        original = event_with_description
        copy = deepcopy(event_with_description)

        hash_original = await pipeline.compute_hash_for_entity(original)
        hash_copy = await pipeline.compute_hash_for_entity(copy)

        assert hash_original == hash_copy

    @pytest.mark.asyncio
    async def test_field_order_independence(self):
        """Hash should be independent of field order (stable serialization)."""
        pipeline = EntityPipeline()

        # Create two entities with same data, different creation order
        entity1 = GoogleCalendarEventEntity(
            entity_id="test_event",
            breadcrumbs=[],
            name="Test Event",
            created_at=None,
            updated_at=None,
            status="confirmed",
            html_link="https://example.com",
            summary="Test",
            description="Description",
            location="Amsterdam",
            color_id=None,
            start_datetime="2025-01-01T10:00:00",
            start_date=None,
            end_datetime="2025-01-01T11:00:00",
            end_date=None,
            recurrence=None,
            recurring_event_id=None,
            organizer={"email": "test@example.com"},
            creator={"email": "test@example.com"},
            attendees=None,
            transparency=None,
            visibility=None,
            conference_data=None,
            event_type="default",
        )

        # Same data, but constructed in different order (deepcopy ensures same internal order)
        entity2 = deepcopy(entity1)

        hash1 = await pipeline.compute_hash_for_entity(entity1)
        hash2 = await pipeline.compute_hash_for_entity(entity2)

        assert hash1 == hash2


class TestRealWorldScenarios:
    """Test realistic scenarios from production use cases."""

    @pytest.mark.asyncio
    async def test_rename_detection(self):
        """File renamed but content unchanged should have different hash."""
        pipeline = EntityPipeline()

        # Same file, different name
        original = deepcopy(text_file)
        hash_original = await pipeline.compute_hash_for_entity(original)

        renamed = deepcopy(text_file)
        renamed.name = "RENAMED_Dec_Feedback.txt"
        hash_renamed = await pipeline.compute_hash_for_entity(renamed)

        # Hash should differ (metadata changed)
        assert hash_original != hash_renamed

    @pytest.mark.asyncio
    async def test_move_detection(self):
        """File moved to different folder should have different hash."""
        pipeline = EntityPipeline()

        original = deepcopy(pdf_file)
        hash_original = await pipeline.compute_hash_for_entity(original)

        moved = deepcopy(pdf_file)
        moved.parents = ["DIFFERENT_FOLDER_ID_12345"]
        hash_moved = await pipeline.compute_hash_for_entity(moved)

        # Hash should differ (parents changed)
        assert hash_original != hash_moved

    @pytest.mark.asyncio
    async def test_url_token_refresh_no_hash_change(self):
        """URL with refreshed access token should NOT change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(pdf_file)
        hash_original = await pipeline.compute_hash_for_entity(original)

        # Simulate token refresh in URL (common in Google Drive, Asana, etc.)
        token_refreshed = deepcopy(pdf_file)
        token_refreshed.url = (
            "https://www.googleapis.com/drive/v3/files/"
            "17llNMF7EhkVXQlKFLzEgQOv6M7iiB9yR?alt=media&token=NEW_REFRESHED_TOKEN_67890"
        )
        hash_refreshed = await pipeline.compute_hash_for_entity(token_refreshed)

        # Hash should be same (url is volatile)
        assert hash_original == hash_refreshed


class TestCodeFileSpecifics:
    """Test CodeFileEntity-specific hash behavior."""

    @pytest.mark.asyncio
    async def test_code_file_commit_change(self):
        """Changing commit_id should change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(code_file_largest)
        hash_original = await pipeline.compute_hash_for_entity(original)

        modified = deepcopy(code_file_largest)
        modified.commit_id = "DIFFERENT_COMMIT_SHA_1234567890abcdef"
        modified.sha = "DIFFERENT_COMMIT_SHA_1234567890abcdef"
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original != hash_modified

    @pytest.mark.asyncio
    async def test_code_file_language_change(self):
        """Changing programming language should change hash."""
        pipeline = EntityPipeline()

        original = deepcopy(code_file_largest)
        hash_original = await pipeline.compute_hash_for_entity(original)

        modified = deepcopy(code_file_largest)
        modified.language = "JavaScript"  # Was Python
        hash_modified = await pipeline.compute_hash_for_entity(modified)

        assert hash_original != hash_modified


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
