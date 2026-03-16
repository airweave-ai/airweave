"""Unit tests for storage backend factory (_create_storage_backend).

Tests the _create_storage_backend() function in core/container/factory.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from airweave.core.config.enums import StorageBackendType
from airweave.core.container.factory import _create_storage_backend


class TestCreateStorageBackend:
    """Test _create_storage_backend factory function."""

    def test_creates_filesystem_backend(self, tmp_path):
        """Test factory creates FilesystemBackend when configured."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.FILESYSTEM
        mock_settings.STORAGE_PATH = str(tmp_path)

        backend = _create_storage_backend(mock_settings)

        from airweave.adapters.storage.filesystem import FilesystemBackend

        assert isinstance(backend, FilesystemBackend)
        assert backend.base_path == tmp_path

    def test_creates_azure_backend(self):
        """Test factory creates AzureBlobBackend when configured."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AZURE
        mock_settings.STORAGE_AZURE_ACCOUNT = "testaccount"
        mock_settings.STORAGE_AZURE_CONTAINER = "testcontainer"
        mock_settings.STORAGE_AZURE_PREFIX = "testprefix"

        backend = _create_storage_backend(mock_settings)

        from airweave.adapters.storage.azure_blob import AzureBlobBackend

        assert isinstance(backend, AzureBlobBackend)
        assert backend.storage_account == "testaccount"
        assert backend.container_name == "testcontainer"
        assert backend.prefix == "testprefix/"

    def test_azure_backend_requires_account(self):
        """Test factory raises error when Azure account is missing."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AZURE
        mock_settings.STORAGE_AZURE_ACCOUNT = None

        with pytest.raises(ValueError) as exc_info:
            _create_storage_backend(mock_settings)

        assert "STORAGE_AZURE_ACCOUNT" in str(exc_info.value)

    def test_creates_s3_backend(self):
        """Test factory creates S3Backend when configured."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = "us-west-2"
        mock_settings.STORAGE_AWS_PREFIX = "testprefix"
        mock_settings.STORAGE_AWS_ENDPOINT_URL = None

        backend = _create_storage_backend(mock_settings)

        from airweave.adapters.storage.aws_s3 import S3Backend

        assert isinstance(backend, S3Backend)
        assert backend.bucket == "testbucket"
        assert backend.region == "us-west-2"
        assert backend.prefix == "testprefix/"

    def test_creates_s3_backend_with_endpoint(self):
        """Test factory creates S3Backend with custom endpoint (MinIO)."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = "us-east-1"
        mock_settings.STORAGE_AWS_PREFIX = ""
        mock_settings.STORAGE_AWS_ENDPOINT_URL = "http://localhost:9000"

        backend = _create_storage_backend(mock_settings)

        from airweave.adapters.storage.aws_s3 import S3Backend

        assert isinstance(backend, S3Backend)
        assert backend.endpoint_url == "http://localhost:9000"

    def test_s3_backend_requires_bucket(self):
        """Test factory raises error when S3 bucket is missing."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = None
        mock_settings.STORAGE_AWS_REGION = "us-east-1"

        with pytest.raises(ValueError) as exc_info:
            _create_storage_backend(mock_settings)

        assert "STORAGE_AWS_BUCKET" in str(exc_info.value)

    def test_s3_backend_requires_region(self):
        """Test factory raises error when S3 region is missing."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = None

        with pytest.raises(ValueError) as exc_info:
            _create_storage_backend(mock_settings)

        assert "STORAGE_AWS_REGION" in str(exc_info.value)

    def test_creates_gcs_backend(self):
        """Test factory creates GCSBackend when configured."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.GCP
        mock_settings.STORAGE_GCP_BUCKET = "testbucket"
        mock_settings.STORAGE_GCP_PROJECT = "testproject"
        mock_settings.STORAGE_GCP_PREFIX = "testprefix"

        backend = _create_storage_backend(mock_settings)

        from airweave.adapters.storage.gcp_gcs import GCSBackend

        assert isinstance(backend, GCSBackend)
        assert backend.bucket_name == "testbucket"
        assert backend.project == "testproject"
        assert backend.prefix == "testprefix/"

    def test_gcs_backend_requires_bucket(self):
        """Test factory raises error when GCS bucket is missing."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.GCP
        mock_settings.STORAGE_GCP_BUCKET = None

        with pytest.raises(ValueError) as exc_info:
            _create_storage_backend(mock_settings)

        assert "STORAGE_GCP_BUCKET" in str(exc_info.value)

    def test_unknown_backend_raises(self):
        """Test factory raises error for unknown backend type."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = "unknown_backend"

        with pytest.raises(ValueError) as exc_info:
            _create_storage_backend(mock_settings)

        assert "Unknown STORAGE_BACKEND" in str(exc_info.value)

    def test_factory_returns_fresh_instance(self, tmp_path):
        """Factory is pure; Container owns the singleton."""
        mock_settings = MagicMock()
        mock_settings.STORAGE_BACKEND = StorageBackendType.FILESYSTEM
        mock_settings.STORAGE_PATH = str(tmp_path)

        backend1 = _create_storage_backend(mock_settings)
        backend2 = _create_storage_backend(mock_settings)

        assert backend1 is not backend2


class TestStorageBackendTypeEnum:
    """Test StorageBackendType enum."""

    def test_enum_values(self):
        """Test that enum has expected values."""
        assert StorageBackendType.FILESYSTEM.value == "filesystem"
        assert StorageBackendType.AZURE.value == "azure"
        assert StorageBackendType.AWS.value == "aws"
        assert StorageBackendType.GCP.value == "gcp"

    def test_all_backends_covered(self):
        """Test that all backend types are implemented."""
        expected = {"filesystem", "azure", "aws", "gcp"}
        actual = {t.value for t in StorageBackendType}
        assert actual == expected
