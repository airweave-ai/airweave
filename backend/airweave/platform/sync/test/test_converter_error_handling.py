"""Tests for converter error handling and skipped entity counting in EntityPipeline.

Tests cover:
- Individual file conversion failures (None results)
- Entire batch converter exceptions
- Multiple converters with mixed success/failure
- Accurate skipped counting
- Proper entity list cleanup
- Textual representation validation

Run with: pytest airweave/platform/sync/test/test_converter_error_handling.py -s -v
"""

import os
import tempfile
from typing import Dict, List
from unittest.mock import patch

import pytest

from airweave.platform.entities._base import FileEntity
from airweave.platform.entities.google_drive import GoogleDriveFileEntity
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.test.mock_context import create_mock_sync_context


class MockConverter:
    """Mock converter that can be configured to succeed/fail per file."""

    def __init__(
        self, name: str, results: Dict[str, str] = None, raise_exception: Exception = None
    ):
        """Initialize mock converter.

        Args:
            name: Converter name for identification
            results: Dict mapping file_path -> content (None = failed file)
            raise_exception: If set, raise this exception instead of returning results
        """
        self.name = name
        self.results = results or {}
        self.raise_exception = raise_exception
        self.call_count = 0

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Mock batch conversion."""
        self.call_count += 1

        if self.raise_exception:
            raise self.raise_exception

        # Return configured results or default to None
        return {path: self.results.get(path) for path in file_paths}


def create_test_file(content: str = "test content") -> str:
    """Create a temporary test file.

    Args:
        content: File content

    Returns:
        Path to temporary file
    """
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, content.encode())
    os.close(fd)
    return path


def create_file_entity(entity_id: str, local_path: str, name: str = None) -> FileEntity:
    """Create a test FileEntity.

    Args:
        entity_id: Entity ID
        local_path: Path to local file
        name: Entity name (defaults to entity_id)

    Returns:
        FileEntity instance
    """
    from datetime import datetime, timezone

    return GoogleDriveFileEntity(
        entity_id=entity_id,
        breadcrumbs=[],
        name=name or entity_id,
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        url=f"https://www.googleapis.com/drive/v3/files/{entity_id}?alt=media",
        local_path=local_path,
        mime_type="text/plain",
        size=100,
        file_type="text",
        description=None,
        starred=False,
        trashed=False,
        explicitly_trashed=False,
        parents=[],
        owners=[],
        shared=False,
        web_view_link=f"https://drive.google.com/file/d/{entity_id}/view?usp=drivesdk",
        icon_link="https://drive-thirdparty.googleusercontent.com/16/type/text/plain",
        md5_checksum="test_checksum",
    )


@pytest.mark.asyncio
class TestConverterErrorHandling:
    """Test suite for converter error handling and skipped counting."""

    async def test_individual_file_failures_counted_correctly(self):
        """Test that individual file failures are counted as skipped."""
        # Create test files
        files = {
            "file1.txt": create_test_file("content 1"),
            "file2.txt": create_test_file("content 2"),
            "file3.txt": create_test_file("content 3"),
        }

        try:
            # Create entities
            entities = [
                create_file_entity("entity1", files["file1.txt"]),
                create_file_entity("entity2", files["file2.txt"]),
                create_file_entity("entity3", files["file3.txt"]),
            ]

            # Configure converter: file2 fails (returns None)
            mock_converter = MockConverter(
                "txt_converter",
                results={
                    files["file1.txt"]: "converted content 1",
                    files["file2.txt"]: None,  # Failed conversion
                    files["file3.txt"]: "converted content 3",
                },
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline and build textual representations
            pipeline = EntityPipeline()

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                return_value=mock_converter,
            ):
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: file2 was skipped
            sync_context.progress.increment.assert_awaited_once_with("skipped", 1)

            # Verify: Only successful entities remain in list
            assert len(entities) == 2
            assert entities[0].entity_id == "entity1"
            assert entities[1].entity_id == "entity3"

            # Verify: Successful entities have textual_representation
            assert hasattr(entities[0], "textual_representation")
            assert "converted content 1" in entities[0].textual_representation
            assert hasattr(entities[1], "textual_representation")
            assert "converted content 3" in entities[1].textual_representation

        finally:
            # Cleanup temp files
            for path in files.values():
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_batch_converter_exception_marks_all_as_failed(self):
        """Test that batch converter exception marks all files as skipped."""
        # Create test files
        files = {
            "file1.txt": create_test_file("content 1"),
            "file2.txt": create_test_file("content 2"),
            "file3.txt": create_test_file("content 3"),
        }

        try:
            # Create entities
            entities = [
                create_file_entity("entity1", files["file1.txt"]),
                create_file_entity("entity2", files["file2.txt"]),
                create_file_entity("entity3", files["file3.txt"]),
            ]

            # Configure converter to raise exception
            mock_converter = MockConverter(
                "txt_converter",
                raise_exception=RuntimeError("Converter batch failed"),
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline and build textual representations
            pipeline = EntityPipeline()

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                return_value=mock_converter,
            ):
                # Should NOT raise exception - errors are handled gracefully
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: ALL files were skipped (3 entities)
            sync_context.progress.increment.assert_awaited_once_with("skipped", 3)

            # Verify: NO entities remain in list (all failed)
            assert len(entities) == 0

        finally:
            # Cleanup temp files
            for path in files.values():
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_multiple_converters_with_mixed_failures(self):
        """Test that failures in one converter don't affect others."""
        # Create test files for different converters
        txt_files = {
            "file1.txt": create_test_file("txt content 1"),
            "file2.txt": create_test_file("txt content 2"),
        }
        # Create files with proper extensions for testing
        fd1, pdf_path1 = tempfile.mkstemp(suffix=".pdf")
        os.write(fd1, b"pdf content 1")
        os.close(fd1)
        fd2, pdf_path2 = tempfile.mkstemp(suffix=".pdf")
        os.write(fd2, b"pdf content 2")
        os.close(fd2)
        pdf_files = {
            "file3.pdf": pdf_path1,
            "file4.pdf": pdf_path2,
        }

        try:
            # Create entities (2 txt, 2 pdf)
            entities = [
                create_file_entity("entity1", txt_files["file1.txt"]),
                create_file_entity("entity2", txt_files["file2.txt"]),
                create_file_entity("entity3", pdf_files["file3.pdf"]),
                create_file_entity("entity4", pdf_files["file4.pdf"]),
            ]

            # Configure converters:
            # - txt_converter: succeeds for all files
            # - pdf_converter: raises exception (all fail)
            txt_converter = MockConverter(
                "txt_converter",
                results={
                    txt_files["file1.txt"]: "converted txt 1",
                    txt_files["file2.txt"]: "converted txt 2",
                },
            )
            pdf_converter = MockConverter(
                "pdf_converter",
                raise_exception=RuntimeError("PDF converter failed"),
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline
            pipeline = EntityPipeline()

            # Mock _determine_converter_for_file to return appropriate converter
            def mock_determine_converter(file_path: str):
                if file_path.endswith(".txt"):
                    return txt_converter
                elif file_path.endswith(".pdf"):
                    return pdf_converter
                else:
                    raise ValueError(f"Unknown extension: {file_path}")

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                side_effect=mock_determine_converter,
            ):
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: Only PDF files were skipped (2 entities)
            sync_context.progress.increment.assert_awaited_once_with("skipped", 2)

            # Verify: Only TXT entities remain (2 entities)
            assert len(entities) == 2
            assert entities[0].entity_id == "entity1"
            assert entities[1].entity_id == "entity2"

            # Verify: TXT entities have textual_representation
            assert "converted txt 1" in entities[0].textual_representation
            assert "converted txt 2" in entities[1].textual_representation

            # Verify: Both converters were called
            assert txt_converter.call_count == 1
            assert pdf_converter.call_count == 1

        finally:
            # Cleanup temp files
            for path in list(txt_files.values()) + list(pdf_files.values()):
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_mixed_individual_and_batch_failures(self):
        """Test combination of individual file failures and batch converter failures."""
        # Create test files for three converters
        txt_files = {
            "file1.txt": create_test_file("txt 1"),
            "file2.txt": create_test_file("txt 2"),
        }
        # Create files with proper extensions
        fd_pdf, pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.write(fd_pdf, b"pdf 1")
        os.close(fd_pdf)
        pdf_files = {
            "file3.pdf": pdf_path,
        }
        fd_docx1, docx_path1 = tempfile.mkstemp(suffix=".docx")
        os.write(fd_docx1, b"docx 1")
        os.close(fd_docx1)
        fd_docx2, docx_path2 = tempfile.mkstemp(suffix=".docx")
        os.write(fd_docx2, b"docx 2")
        os.close(fd_docx2)
        docx_files = {
            "file4.docx": docx_path1,
            "file5.docx": docx_path2,
        }

        try:
            # Create entities
            entities = [
                create_file_entity("entity1", txt_files["file1.txt"]),
                create_file_entity("entity2", txt_files["file2.txt"]),
                create_file_entity("entity3", pdf_files["file3.pdf"]),
                create_file_entity("entity4", docx_files["file4.docx"]),
                create_file_entity("entity5", docx_files["file5.docx"]),
            ]

            # Configure converters:
            # - txt_converter: file1 succeeds, file2 fails (returns None)
            # - pdf_converter: raises exception (batch fails)
            # - docx_converter: both succeed
            txt_converter = MockConverter(
                "txt_converter",
                results={
                    txt_files["file1.txt"]: "converted txt 1",
                    txt_files["file2.txt"]: None,  # Individual failure
                },
            )
            pdf_converter = MockConverter(
                "pdf_converter",
                raise_exception=RuntimeError("PDF batch failed"),
            )
            docx_converter = MockConverter(
                "docx_converter",
                results={
                    docx_files["file4.docx"]: "converted docx 1",
                    docx_files["file5.docx"]: "converted docx 2",
                },
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline
            pipeline = EntityPipeline()

            # Mock _determine_converter_for_file
            def mock_determine_converter(file_path: str):
                if file_path.endswith(".txt"):
                    return txt_converter
                elif file_path.endswith(".pdf"):
                    return pdf_converter
                elif file_path.endswith(".docx"):
                    return docx_converter
                else:
                    raise ValueError(f"Unknown extension: {file_path}")

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                side_effect=mock_determine_converter,
            ):
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: 2 entities skipped (file2.txt + file3.pdf)
            # - file1.txt: success (0)
            # - file2.txt: individual failure (1)
            # - file3.pdf: batch failure (1)
            # - file4.docx, file5.docx: success (0)
            # Total: 2 skipped
            sync_context.progress.increment.assert_awaited_once_with("skipped", 2)

            # Verify: 3 entities remain (entity1, entity4, entity5)
            assert len(entities) == 3
            assert entities[0].entity_id == "entity1"
            assert entities[1].entity_id == "entity4"
            assert entities[2].entity_id == "entity5"

            # Verify: Remaining entities have textual_representation
            assert "converted txt 1" in entities[0].textual_representation
            assert "converted docx 1" in entities[1].textual_representation
            assert "converted docx 2" in entities[2].textual_representation

        finally:
            # Cleanup temp files
            for path in (
                list(txt_files.values()) + list(pdf_files.values()) + list(docx_files.values())
            ):
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_non_file_entities_not_affected_by_converter_failures(self):
        """Test that non-FileEntity entities are unaffected by converter failures."""
        from airweave.platform.entities.google_calendar import GoogleCalendarEventEntity

        # Create test files
        files = {
            "file1.txt": create_test_file("content 1"),
        }

        try:
            # Mix of FileEntity and non-FileEntity
            entities = [
                GoogleCalendarEventEntity(
                    entity_id="event1",
                    breadcrumbs=[],
                    name="Meeting",
                    summary="Team meeting",
                    start="2025-01-01T10:00:00Z",
                    end="2025-01-01T11:00:00Z",
                ),
                create_file_entity("file1", files["file1.txt"]),
                GoogleCalendarEventEntity(
                    entity_id="event2",
                    breadcrumbs=[],
                    name="Call",
                    summary="Client call",
                    start="2025-01-01T14:00:00Z",
                    end="2025-01-01T15:00:00Z",
                ),
            ]

            # Configure converter to fail
            mock_converter = MockConverter(
                "txt_converter",
                raise_exception=RuntimeError("Converter failed"),
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline
            pipeline = EntityPipeline()

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                return_value=mock_converter,
            ):
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: Only the file entity was skipped (1)
            sync_context.progress.increment.assert_awaited_once_with("skipped", 1)

            # Verify: Non-file entities remain (2 events)
            assert len(entities) == 2
            assert entities[0].entity_id == "event1"
            assert entities[1].entity_id == "event2"

            # Verify: Non-file entities have metadata (but no file content)
            assert hasattr(entities[0], "textual_representation")
            assert "Meeting" in entities[0].textual_representation
            assert hasattr(entities[1], "textual_representation")
            assert "Client call" in entities[1].textual_representation

        finally:
            # Cleanup temp files
            for path in files.values():
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_all_entities_fail_results_in_empty_list(self):
        """Test that if all entities fail, list is empty and all counted as skipped."""
        # Create test files
        files = {
            "file1.txt": create_test_file("content 1"),
            "file2.txt": create_test_file("content 2"),
        }

        try:
            # Create entities
            entities = [
                create_file_entity("entity1", files["file1.txt"]),
                create_file_entity("entity2", files["file2.txt"]),
            ]

            # Configure converter to fail all
            mock_converter = MockConverter(
                "txt_converter",
                results={
                    files["file1.txt"]: None,
                    files["file2.txt"]: None,
                },
            )

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline
            pipeline = EntityPipeline()

            with patch.object(
                pipeline,
                "_determine_converter_for_file",
                return_value=mock_converter,
            ):
                await pipeline._build_textual_representations(entities, sync_context)

            # Verify: Both entities skipped
            sync_context.progress.increment.assert_awaited_once_with("skipped", 2)

            # Verify: No entities remain
            assert len(entities) == 0

        finally:
            # Cleanup temp files
            for path in files.values():
                try:
                    os.unlink(path)
                except Exception:
                    pass

    async def test_empty_textual_representation_after_metadata_fails(self):
        """Test that entities with only metadata (empty content) are handled correctly."""
        from airweave.platform.entities.google_calendar import GoogleCalendarEventEntity

        # Create entity without embeddable fields
        entities = [
            GoogleCalendarEventEntity(
                entity_id="event1",
                breadcrumbs=[],
                name="",  # Empty name
                summary="",  # Empty summary
                start="2025-01-01T10:00:00Z",
                end="2025-01-01T11:00:00Z",
            ),
        ]

        # Setup mock context
        sync_context = create_mock_sync_context()

        # Create pipeline
        pipeline = EntityPipeline()

        # This should NOT fail - even with minimal metadata
        await pipeline._build_textual_representations(entities, sync_context)

        # Verify: Entity still has textual_representation (even if minimal)
        assert len(entities) == 1
        assert hasattr(entities[0], "textual_representation")
        # Metadata section should exist even if fields are empty
        assert "# Metadata" in entities[0].textual_representation

    async def test_skipped_counting_with_unsupported_file_type(self):
        """Test that unsupported file types are properly skipped and counted."""
        # Create unsupported file type
        fd, unsupported_path = tempfile.mkstemp(suffix=".xyz")
        os.write(fd, b"unsupported content")
        os.close(fd)

        try:
            # Create entity with unsupported file
            entities = [
                create_file_entity("entity1", unsupported_path),
            ]

            # Setup mock context
            sync_context = create_mock_sync_context()

            # Create pipeline
            pipeline = EntityPipeline()

            # _determine_converter_for_file should raise EntityProcessingError for .xyz
            await pipeline._build_textual_representations(entities, sync_context)

            # Verify: Entity was skipped
            sync_context.progress.increment.assert_awaited_once_with("skipped", 1)

            # Verify: No entities remain
            assert len(entities) == 0

        finally:
            try:
                os.unlink(unsupported_path)
            except Exception:
                pass
