"""Unit tests for FileService — save_bytes, restore_from_arf, cleanup, validation."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.storage.exceptions import FileSkippedException
from airweave.domains.storage.file_service import FileService


def _make_service(tmpdir: str) -> FileService:
    """Create FileService with a real temp dir and mock storage backend."""
    sync_job_id = uuid4()
    storage = MagicMock()
    storage.read_file = AsyncMock()
    storage.write_file = AsyncMock()
    storage.delete_directory = AsyncMock()

    with patch(
        "airweave.domains.storage.file_service.paths.temp_sync_dir", return_value=tmpdir
    ):
        svc = FileService(sync_job_id=sync_job_id, storage_backend=storage)

    return svc, storage


class TestSaveBytes:
    @pytest.mark.asyncio
    async def test_saves_pdf_bytes_and_sets_local_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)
            entity = MagicMock()
            logger = MagicMock()

            result = await svc.save_bytes(
                entity=entity,
                content=b"%PDF-1.4 test content",
                filename_with_extension="report.pdf",
                logger=logger,
            )

            assert result is entity
            assert entity.local_path is not None
            assert entity.local_path.endswith(".pdf")
            assert os.path.exists(entity.local_path)

    @pytest.mark.asyncio
    async def test_raises_file_skipped_for_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)

            with pytest.raises(FileSkippedException, match="Unsupported"):
                await svc.save_bytes(
                    entity=MagicMock(),
                    content=b"binary",
                    filename_with_extension="file.xyz_unsupported",
                    logger=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)

            with pytest.raises(ValueError, match="must include file extension"):
                await svc.save_bytes(
                    entity=MagicMock(),
                    content=b"data",
                    filename_with_extension="no_extension",
                    logger=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_raises_file_skipped_for_oversized_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)
            huge = b"x" * (FileService.MAX_FILE_SIZE_BYTES + 1)

            with pytest.raises(FileSkippedException, match="too large"):
                await svc.save_bytes(
                    entity=MagicMock(),
                    content=huge,
                    filename_with_extension="giant.pdf",
                    logger=MagicMock(),
                )


class TestRestoreFromArf:
    @pytest.mark.asyncio
    async def test_restores_file_to_temp_and_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, storage = _make_service(tmpdir)
            storage.read_file = AsyncMock(return_value=b"file content here")

            path = await svc.restore_from_arf(
                arf_file_path="raw/sync-123/files/entity.pdf",
                filename="report.pdf",
                logger=MagicMock(),
            )

            assert path.startswith(tmpdir)
            assert path.endswith(".pdf")
            assert os.path.exists(path)
            storage.read_file.assert_awaited_once_with("raw/sync-123/files/entity.pdf")


class TestCleanupSyncDirectory:
    @pytest.mark.asyncio
    async def test_removes_existing_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)
            # Create a file inside to confirm removal
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")

            await svc.cleanup_sync_directory(logger=MagicMock())

            assert not os.path.exists(tmpdir)

    @pytest.mark.asyncio
    async def test_does_not_raise_when_dir_already_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc, _ = _make_service(tmpdir)

        # tmpdir has been deleted by the context manager exit
        await svc.cleanup_sync_directory(logger=MagicMock())
