"""Integration tests for FilesystemBackend.

Tests run against the local filesystem using pytest's tmp_path fixture.
"""

import pytest
import pytest_asyncio

from .base_tests import BaseStorageBackendTests


@pytest_asyncio.fixture
async def backend(filesystem_backend):
    """Provide the backend fixture for base tests."""
    return filesystem_backend


class TestFilesystemBackend(BaseStorageBackendTests):
    """FilesystemBackend tests - inherits all tests from BaseStorageBackendTests."""

    pass
