"""Base test class for storage backend integration tests.

All storage backends (Filesystem, S3, Azure, GCS) share the same interface
defined by the StorageBackend protocol. This base class contains common tests
that verify any backend implementation works correctly.

Usage:
    class TestMyBackend(BaseStorageBackendTests):
        # pytest will run all inherited tests using the `backend` fixture
        pass

Each backend's test file should provide a `backend` fixture that returns
the specific backend instance configured for that test.
"""

import asyncio
from abc import ABC

import pytest


class BaseStorageBackendTests(ABC):
    """Base test class for all storage backend implementations.

    Subclasses must provide a `backend` fixture that returns the storage backend
    to test. Tests use a `test_prefix` fixture for path isolation.
    """

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    @pytest.mark.asyncio
    async def test_write_and_read_json(self, backend, test_prefix, test_data):
        """Test writing and reading JSON data."""
        path = f"{test_prefix}/data.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, backend, test_prefix, test_binary):
        """Test writing and reading binary data."""
        path = f"{test_prefix}/binary.bin"

        await backend.write_file(path, test_binary)
        result = await backend.read_file(path)

        assert result == test_binary

    @pytest.mark.asyncio
    async def test_exists(self, backend, test_prefix, test_data):
        """Test checking file/object existence."""
        path = f"{test_prefix}/exists.json"

        # Should not exist initially
        assert await backend.exists(path) is False

        # Create file
        await backend.write_json(path, test_data)

        # Should exist now
        assert await backend.exists(path) is True

    @pytest.mark.asyncio
    async def test_delete_file(self, backend, test_prefix, test_data):
        """Test deleting a single file/object."""
        path = f"{test_prefix}/delete-me.json"

        await backend.write_json(path, test_data)
        assert await backend.exists(path) is True

        result = await backend.delete(path)
        assert result is True
        assert await backend.exists(path) is False

    @pytest.mark.asyncio
    async def test_delete_directory(self, backend, test_prefix, test_data):
        """Test deleting a directory/prefix recursively."""
        # Create multiple files
        await backend.write_json(f"{test_prefix}/dir/file1.json", test_data)
        await backend.write_json(f"{test_prefix}/dir/file2.json", test_data)
        await backend.write_json(f"{test_prefix}/dir/subdir/file3.json", test_data)

        # Delete directory
        result = await backend.delete(f"{test_prefix}/dir")
        assert result is True

        # All files should be gone
        assert await backend.exists(f"{test_prefix}/dir/file1.json") is False
        assert await backend.exists(f"{test_prefix}/dir/file2.json") is False
        assert await backend.exists(f"{test_prefix}/dir/subdir/file3.json") is False

    # =========================================================================
    # Listing Operations
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_files(self, backend, test_prefix, test_data):
        """Test listing files under a prefix."""
        # Create files
        await backend.write_json(f"{test_prefix}/list/a.json", test_data)
        await backend.write_json(f"{test_prefix}/list/b.json", test_data)
        await backend.write_json(f"{test_prefix}/list/subdir/c.json", test_data)

        files = await backend.list_files(f"{test_prefix}/list")

        assert f"{test_prefix}/list/a.json" in files
        assert f"{test_prefix}/list/b.json" in files
        assert f"{test_prefix}/list/subdir/c.json" in files

    @pytest.mark.asyncio
    async def test_list_dirs(self, backend, test_prefix, test_data):
        """Test listing immediate subdirectories."""
        # Create files in subdirectories
        await backend.write_json(f"{test_prefix}/dirs/dir1/file.json", test_data)
        await backend.write_json(f"{test_prefix}/dirs/dir2/file.json", test_data)
        await backend.write_json(f"{test_prefix}/dirs/file.json", test_data)

        dirs = await backend.list_dirs(f"{test_prefix}/dirs")

        assert f"{test_prefix}/dirs/dir1" in dirs
        assert f"{test_prefix}/dirs/dir2" in dirs

    @pytest.mark.asyncio
    async def test_count_files(self, backend, test_prefix, test_data):
        """Test counting files with pattern matching."""
        # Create mix of files
        await backend.write_json(f"{test_prefix}/count/a.json", test_data)
        await backend.write_json(f"{test_prefix}/count/b.json", test_data)
        await backend.write_file(f"{test_prefix}/count/c.txt", b"text")

        # Count all files
        all_count = await backend.count_files(f"{test_prefix}/count")
        assert all_count == 3

        # Count only JSON files
        json_count = await backend.count_files(f"{test_prefix}/count", "*.json")
        assert json_count == 2

    # =========================================================================
    # Error Handling
    # =========================================================================

    @pytest.mark.asyncio
    async def test_read_nonexistent_json_raises(
        self, backend, test_prefix, storage_not_found_error
    ):
        """Test that reading nonexistent JSON raises StorageNotFoundError."""
        with pytest.raises(storage_not_found_error):
            await backend.read_json(f"{test_prefix}/nonexistent.json")

    @pytest.mark.asyncio
    async def test_read_nonexistent_file_raises(
        self, backend, test_prefix, storage_not_found_error
    ):
        """Test that reading nonexistent file raises StorageNotFoundError."""
        with pytest.raises(storage_not_found_error):
            await backend.read_file(f"{test_prefix}/nonexistent.bin")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, backend, test_prefix):
        """Test that deleting nonexistent file returns False."""
        result = await backend.delete(f"{test_prefix}/nonexistent.json")
        assert result is False

    # =========================================================================
    # Edge Cases
    # =========================================================================

    @pytest.mark.asyncio
    async def test_nested_paths(self, backend, test_prefix, test_data):
        """Test deeply nested directory structures."""
        path = f"{test_prefix}/a/b/c/d/e/f/g/deep.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_special_characters_in_path(self, backend, test_prefix, test_data):
        """Test paths with spaces and special characters."""
        path = f"{test_prefix}/path with spaces/file-name_v2.json"

        await backend.write_json(path, test_data)
        result = await backend.read_json(path)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_large_file(self, backend, test_prefix, large_binary):
        """Test handling files larger than 1MB."""
        path = f"{test_prefix}/large.bin"

        await backend.write_file(path, large_binary)
        result = await backend.read_file(path)

        assert result == large_binary
        assert len(result) > 1024 * 1024

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, backend, test_prefix, test_data):
        """Test multiple concurrent async operations."""
        paths = [f"{test_prefix}/concurrent/{i}.json" for i in range(10)]

        # Write concurrently
        await asyncio.gather(*[backend.write_json(p, test_data) for p in paths])

        # Read concurrently
        results = await asyncio.gather(*[backend.read_json(p) for p in paths])

        assert all(r == test_data for r in results)

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, backend, test_prefix):
        """Test overwriting an existing file."""
        path = f"{test_prefix}/overwrite.json"

        await backend.write_json(path, {"version": 1})
        await backend.write_json(path, {"version": 2})

        result = await backend.read_json(path)
        assert result == {"version": 2}
