"""Unit tests for FilesystemBackend.

These tests use pytest's tmp_path fixture and don't require any external resources.
"""

import asyncio
import json
import os

import pytest

from airweave.platform.storage.backends.filesystem import FilesystemBackend
from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)


@pytest.fixture
def backend(tmp_path):
    """Create a FilesystemBackend for testing."""
    return FilesystemBackend(base_path=tmp_path)


class TestFilesystemBackendInit:
    """Test FilesystemBackend initialization."""

    def test_init_creates_base_directory(self, tmp_path):
        """Test that init creates the base directory if it doesn't exist."""
        new_path = tmp_path / "new_storage"
        assert not new_path.exists()

        backend = FilesystemBackend(base_path=new_path)

        assert new_path.exists()
        assert backend.base_path == new_path

    def test_init_with_string_path(self, tmp_path):
        """Test initialization with string path."""
        backend = FilesystemBackend(base_path=str(tmp_path))
        assert backend.base_path == tmp_path

    def test_resolve_normalizes_path_separators(self, tmp_path):
        """Test that _resolve normalizes forward slashes to OS separators."""
        backend = FilesystemBackend(base_path=tmp_path)
        resolved = backend._resolve("a/b/c")

        expected = tmp_path / "a" / "b" / "c"
        assert resolved == expected


class TestFilesystemBackendWriteJson:
    """Test write_json method."""

    @pytest.mark.asyncio
    async def test_write_json_creates_file(self, backend, tmp_path, test_data):
        """Test that write_json creates the file with correct content."""
        path = "data.json"

        await backend.write_json(path, test_data)

        full_path = tmp_path / path
        assert full_path.exists()
        with open(full_path) as f:
            content = json.load(f)
        assert content == test_data

    @pytest.mark.asyncio
    async def test_write_json_creates_parent_directories(self, backend, tmp_path, test_data):
        """Test that write_json creates nested directories."""
        path = "deep/nested/path/data.json"

        await backend.write_json(path, test_data)

        full_path = tmp_path / "deep" / "nested" / "path" / "data.json"
        assert full_path.exists()

    @pytest.mark.asyncio
    async def test_write_json_overwrites_existing(self, backend):
        """Test that write_json overwrites existing files."""
        path = "data.json"

        await backend.write_json(path, {"version": 1})
        await backend.write_json(path, {"version": 2})

        result = await backend.read_json(path)
        assert result == {"version": 2}

    @pytest.mark.asyncio
    async def test_write_json_with_unicode(self, backend):
        """Test writing JSON with unicode characters."""
        data = {"emoji": "🚀", "japanese": "こんにちは", "arabic": "مرحبا"}

        await backend.write_json("unicode.json", data)
        result = await backend.read_json("unicode.json")

        assert result == data

    @pytest.mark.asyncio
    async def test_write_json_serializes_datetime(self, backend):
        """Test that write_json serializes non-standard types using default=str."""
        from datetime import datetime

        data = {"timestamp": datetime(2024, 1, 15, 10, 30, 0)}

        await backend.write_json("datetime.json", data)
        result = await backend.read_json("datetime.json")

        assert "2024-01-15" in result["timestamp"]


class TestFilesystemBackendReadJson:
    """Test read_json method."""

    @pytest.mark.asyncio
    async def test_read_json_returns_dict(self, backend, test_data):
        """Test that read_json returns the correct dict."""
        await backend.write_json("data.json", test_data)

        result = await backend.read_json("data.json")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_read_json_nonexistent_raises(self, backend):
        """Test that reading nonexistent file raises StorageNotFoundError."""
        with pytest.raises(StorageNotFoundError) as exc_info:
            await backend.read_json("nonexistent.json")

        assert "Path not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_json_invalid_json_raises(self, backend, tmp_path):
        """Test that reading invalid JSON raises StorageException."""
        # Create a file with invalid JSON
        path = tmp_path / "invalid.json"
        path.write_text("not valid json {{{")

        with pytest.raises(StorageException) as exc_info:
            await backend.read_json("invalid.json")

        assert "Invalid JSON" in str(exc_info.value)


class TestFilesystemBackendWriteFile:
    """Test write_file method."""

    @pytest.mark.asyncio
    async def test_write_file_creates_file(self, backend, tmp_path, test_binary):
        """Test that write_file creates the file with correct content."""
        path = "data.bin"

        await backend.write_file(path, test_binary)

        full_path = tmp_path / path
        assert full_path.exists()
        assert full_path.read_bytes() == test_binary

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_directories(self, backend, tmp_path, test_binary):
        """Test that write_file creates nested directories."""
        path = "deep/nested/data.bin"

        await backend.write_file(path, test_binary)

        full_path = tmp_path / "deep" / "nested" / "data.bin"
        assert full_path.exists()

    @pytest.mark.asyncio
    async def test_write_file_empty_content(self, backend):
        """Test writing empty content."""
        await backend.write_file("empty.bin", b"")

        result = await backend.read_file("empty.bin")
        assert result == b""

    @pytest.mark.asyncio
    async def test_write_file_large_content(self, backend, large_binary):
        """Test writing large binary content (>1MB)."""
        await backend.write_file("large.bin", large_binary)

        result = await backend.read_file("large.bin")
        assert result == large_binary
        assert len(result) > 1024 * 1024


class TestFilesystemBackendReadFile:
    """Test read_file method."""

    @pytest.mark.asyncio
    async def test_read_file_returns_bytes(self, backend, test_binary):
        """Test that read_file returns the correct bytes."""
        await backend.write_file("data.bin", test_binary)

        result = await backend.read_file("data.bin")

        assert result == test_binary

    @pytest.mark.asyncio
    async def test_read_file_nonexistent_raises(self, backend):
        """Test that reading nonexistent file raises StorageNotFoundError."""
        with pytest.raises(StorageNotFoundError) as exc_info:
            await backend.read_file("nonexistent.bin")

        assert "Path not found" in str(exc_info.value)


class TestFilesystemBackendExists:
    """Test exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent(self, backend):
        """Test exists returns False for nonexistent paths."""
        result = await backend.exists("nonexistent.json")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_file(self, backend, test_data):
        """Test exists returns True for existing file."""
        await backend.write_json("data.json", test_data)

        result = await backend.exists("data.json")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_directory(self, backend, test_data):
        """Test exists returns True for existing directory."""
        await backend.write_json("dir/data.json", test_data)

        result = await backend.exists("dir")
        assert result is True


class TestFilesystemBackendDelete:
    """Test delete method."""

    @pytest.mark.asyncio
    async def test_delete_file_returns_true(self, backend, test_data):
        """Test deleting a file returns True."""
        await backend.write_json("data.json", test_data)

        result = await backend.delete("data.json")

        assert result is True
        assert await backend.exists("data.json") is False

    @pytest.mark.asyncio
    async def test_delete_directory_returns_true(self, backend, test_data):
        """Test deleting a directory returns True and removes all contents."""
        await backend.write_json("dir/file1.json", test_data)
        await backend.write_json("dir/file2.json", test_data)
        await backend.write_json("dir/subdir/file3.json", test_data)

        result = await backend.delete("dir")

        assert result is True
        assert await backend.exists("dir") is False
        assert await backend.exists("dir/file1.json") is False
        assert await backend.exists("dir/subdir/file3.json") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, backend):
        """Test deleting nonexistent path returns False."""
        result = await backend.delete("nonexistent.json")
        assert result is False


class TestFilesystemBackendListFiles:
    """Test list_files method."""

    @pytest.mark.asyncio
    async def test_list_files_returns_all_files(self, backend, test_data):
        """Test list_files returns all files under prefix."""
        await backend.write_json("prefix/a.json", test_data)
        await backend.write_json("prefix/b.json", test_data)
        await backend.write_json("prefix/subdir/c.json", test_data)

        files = await backend.list_files("prefix")

        assert "prefix/a.json" in files
        assert "prefix/b.json" in files
        assert "prefix/subdir/c.json" in files
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_list_files_empty_prefix(self, backend, test_data):
        """Test list_files with empty prefix returns all files."""
        await backend.write_json("file1.json", test_data)
        await backend.write_json("dir/file2.json", test_data)

        files = await backend.list_files("")

        assert "file1.json" in files
        assert "dir/file2.json" in files

    @pytest.mark.asyncio
    async def test_list_files_nonexistent_prefix(self, backend):
        """Test list_files returns empty list for nonexistent prefix."""
        files = await backend.list_files("nonexistent")
        assert files == []

    @pytest.mark.asyncio
    async def test_list_files_returns_sorted(self, backend, test_data):
        """Test list_files returns sorted file list."""
        await backend.write_json("prefix/c.json", test_data)
        await backend.write_json("prefix/a.json", test_data)
        await backend.write_json("prefix/b.json", test_data)

        files = await backend.list_files("prefix")

        assert files == sorted(files)


class TestFilesystemBackendListDirs:
    """Test list_dirs method."""

    @pytest.mark.asyncio
    async def test_list_dirs_returns_immediate_subdirs(self, backend, test_data):
        """Test list_dirs returns only immediate subdirectories."""
        await backend.write_json("prefix/dir1/file.json", test_data)
        await backend.write_json("prefix/dir2/file.json", test_data)
        await backend.write_json("prefix/dir1/subdir/file.json", test_data)
        await backend.write_json("prefix/file.json", test_data)

        dirs = await backend.list_dirs("prefix")

        assert "prefix/dir1" in dirs
        assert "prefix/dir2" in dirs
        # subdir should NOT be in the list (only immediate subdirs)
        assert "prefix/dir1/subdir" not in dirs
        # file.json should not appear
        assert len([d for d in dirs if "file.json" in d]) == 0

    @pytest.mark.asyncio
    async def test_list_dirs_nonexistent_prefix(self, backend):
        """Test list_dirs returns empty list for nonexistent prefix."""
        dirs = await backend.list_dirs("nonexistent")
        assert dirs == []

    @pytest.mark.asyncio
    async def test_list_dirs_returns_sorted(self, backend, test_data):
        """Test list_dirs returns sorted directory list."""
        await backend.write_json("prefix/charlie/file.json", test_data)
        await backend.write_json("prefix/alpha/file.json", test_data)
        await backend.write_json("prefix/bravo/file.json", test_data)

        dirs = await backend.list_dirs("prefix")

        assert dirs == sorted(dirs)


class TestFilesystemBackendCountFiles:
    """Test count_files method."""

    @pytest.mark.asyncio
    async def test_count_files_returns_correct_count(self, backend, test_data):
        """Test count_files returns correct count."""
        await backend.write_json("prefix/a.json", test_data)
        await backend.write_json("prefix/b.json", test_data)
        await backend.write_file("prefix/c.txt", b"text")

        count = await backend.count_files("prefix")

        assert count == 3

    @pytest.mark.asyncio
    async def test_count_files_with_pattern(self, backend, test_data):
        """Test count_files with pattern filter."""
        await backend.write_json("prefix/a.json", test_data)
        await backend.write_json("prefix/b.json", test_data)
        await backend.write_file("prefix/c.txt", b"text")

        json_count = await backend.count_files("prefix", "*.json")

        assert json_count == 2

    @pytest.mark.asyncio
    async def test_count_files_nonexistent_prefix(self, backend):
        """Test count_files returns 0 for nonexistent prefix."""
        count = await backend.count_files("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_files_recursive(self, backend, test_data):
        """Test count_files counts files in subdirectories."""
        await backend.write_json("prefix/a.json", test_data)
        await backend.write_json("prefix/subdir/b.json", test_data)
        await backend.write_json("prefix/subdir/deep/c.json", test_data)

        count = await backend.count_files("prefix")

        assert count == 3


class TestFilesystemBackendEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_deeply_nested_paths(self, backend, test_data):
        """Test deeply nested directory structures."""
        path = "a/b/c/d/e/f/g/h/i/j/deep.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_paths_with_spaces(self, backend, test_data):
        """Test paths containing spaces."""
        path = "path with spaces/file name.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_paths_with_special_characters(self, backend, test_data):
        """Test paths with hyphens, underscores, and dots."""
        path = "my-path_v2/file.backup.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, backend, test_data):
        """Test concurrent write operations don't interfere."""
        paths = [f"concurrent/{i}.json" for i in range(20)]

        await asyncio.gather(*[backend.write_json(p, test_data) for p in paths])

        for path in paths:
            result = await backend.read_json(path)
            assert result == test_data

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, backend, test_data):
        """Test concurrent read operations."""
        path = "shared.json"
        await backend.write_json(path, test_data)

        results = await asyncio.gather(*[backend.read_json(path) for _ in range(20)])

        assert all(r == test_data for r in results)

    @pytest.mark.asyncio
    async def test_mixed_operations(self, backend, test_data):
        """Test mixed read/write/delete operations."""
        await backend.write_json("file1.json", test_data)
        await backend.write_json("file2.json", test_data)

        assert await backend.exists("file1.json")
        await backend.delete("file1.json")
        assert not await backend.exists("file1.json")

        result = await backend.read_json("file2.json")
        assert result == test_data


class TestFilesystemBackendProtocolCompliance:
    """Verify FilesystemBackend implements StorageBackend protocol."""

    def test_implements_protocol(self, backend):
        """Test that FilesystemBackend is instance of StorageBackend protocol."""
        from airweave.platform.storage.protocol import StorageBackend

        assert isinstance(backend, StorageBackend)

    def test_has_all_required_methods(self, backend):
        """Test that backend has all required protocol methods."""
        required_methods = [
            "write_json",
            "read_json",
            "write_file",
            "read_file",
            "exists",
            "delete",
            "list_files",
            "list_dirs",
            "count_files",
        ]
        for method in required_methods:
            assert hasattr(backend, method)
            assert callable(getattr(backend, method))
