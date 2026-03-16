"""Unit tests for SyncFileManager constructor injection."""

from pathlib import Path

import pytest

from airweave.domains.storage.fakes import FakeStorageBackend
from airweave.domains.storage.paths import StoragePaths
from airweave.domains.storage.sync_file_manager import SyncFileManager


def test_default_temp_cache_dir():
    mgr = SyncFileManager(backend=FakeStorageBackend())
    assert mgr.temp_cache_dir == Path(StoragePaths.TEMP_CACHE)


def test_injectable_temp_cache_dir(tmp_path):
    custom = tmp_path / "my_cache"
    mgr = SyncFileManager(backend=FakeStorageBackend(), temp_cache_dir=custom)
    assert mgr.temp_cache_dir == custom
    assert custom.exists()
