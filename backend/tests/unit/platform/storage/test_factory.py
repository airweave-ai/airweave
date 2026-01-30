"""Unit tests for storage backend factory.

Tests the get_storage_backend() factory function with mocked settings.
"""

from unittest.mock import MagicMock, patch

import pytest

from airweave.core.config.enums import StorageBackendType


class TestGetStorageBackend:
    """Test get_storage_backend factory function."""

    def setup_method(self):
        """Clear the factory cache before each test."""
        from airweave.platform.storage.factory import get_storage_backend

        get_storage_backend.cache_clear()

    def teardown_method(self):
        """Clear the factory cache after each test."""
        from airweave.platform.storage.factory import get_storage_backend

        get_storage_backend.cache_clear()

    @patch("airweave.platform.storage.factory.settings")
    def test_creates_filesystem_backend(self, mock_settings, tmp_path):
        """Test factory creates FilesystemBackend when configured."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.FILESYSTEM
        mock_settings.STORAGE_PATH = str(tmp_path)

        from airweave.platform.storage.factory import get_storage_backend

        backend = get_storage_backend()

        from airweave.platform.storage.backends.filesystem import FilesystemBackend

        assert isinstance(backend, FilesystemBackend)
        assert backend.base_path == tmp_path

    @patch("airweave.platform.storage.factory.settings")
    def test_creates_azure_backend(self, mock_settings):
        """Test factory creates AzureBlobBackend when configured."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AZURE
        mock_settings.STORAGE_AZURE_ACCOUNT = "testaccount"
        mock_settings.STORAGE_AZURE_CONTAINER = "testcontainer"
        mock_settings.STORAGE_AZURE_PREFIX = "testprefix"

        from airweave.platform.storage.factory import get_storage_backend

        backend = get_storage_backend()

        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        assert isinstance(backend, AzureBlobBackend)
        assert backend.storage_account == "testaccount"
        assert backend.container_name == "testcontainer"
        assert backend.prefix == "testprefix/"

    @patch("airweave.platform.storage.factory.settings")
    def test_azure_backend_requires_account(self, mock_settings):
        """Test factory raises error when Azure account is missing."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AZURE
        mock_settings.STORAGE_AZURE_ACCOUNT = None

        from airweave.platform.storage.factory import get_storage_backend

        with pytest.raises(ValueError) as exc_info:
            get_storage_backend()

        assert "STORAGE_AZURE_ACCOUNT" in str(exc_info.value)

    @patch("airweave.platform.storage.factory.settings")
    def test_creates_s3_backend(self, mock_settings):
        """Test factory creates S3Backend when configured."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = "us-west-2"
        mock_settings.STORAGE_AWS_PREFIX = "testprefix"
        mock_settings.STORAGE_AWS_ENDPOINT_URL = None

        from airweave.platform.storage.factory import get_storage_backend

        backend = get_storage_backend()

        from airweave.platform.storage.backends.aws_s3 import S3Backend

        assert isinstance(backend, S3Backend)
        assert backend.bucket == "testbucket"
        assert backend.region == "us-west-2"
        assert backend.prefix == "testprefix/"

    @patch("airweave.platform.storage.factory.settings")
    def test_creates_s3_backend_with_endpoint(self, mock_settings):
        """Test factory creates S3Backend with custom endpoint (MinIO)."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = "us-east-1"
        mock_settings.STORAGE_AWS_PREFIX = ""
        mock_settings.STORAGE_AWS_ENDPOINT_URL = "http://localhost:9000"

        from airweave.platform.storage.factory import get_storage_backend

        backend = get_storage_backend()

        from airweave.platform.storage.backends.aws_s3 import S3Backend

        assert isinstance(backend, S3Backend)
        assert backend.endpoint_url == "http://localhost:9000"

    @patch("airweave.platform.storage.factory.settings")
    def test_s3_backend_requires_bucket(self, mock_settings):
        """Test factory raises error when S3 bucket is missing."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = None
        mock_settings.STORAGE_AWS_REGION = "us-east-1"

        from airweave.platform.storage.factory import get_storage_backend

        with pytest.raises(ValueError) as exc_info:
            get_storage_backend()

        assert "STORAGE_AWS_BUCKET" in str(exc_info.value)

    @patch("airweave.platform.storage.factory.settings")
    def test_s3_backend_requires_region(self, mock_settings):
        """Test factory raises error when S3 region is missing."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.AWS
        mock_settings.STORAGE_AWS_BUCKET = "testbucket"
        mock_settings.STORAGE_AWS_REGION = None

        from airweave.platform.storage.factory import get_storage_backend

        with pytest.raises(ValueError) as exc_info:
            get_storage_backend()

        assert "STORAGE_AWS_REGION" in str(exc_info.value)

    @patch("airweave.platform.storage.factory.settings")
    def test_creates_gcs_backend(self, mock_settings):
        """Test factory creates GCSBackend when configured."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.GCP
        mock_settings.STORAGE_GCP_BUCKET = "testbucket"
        mock_settings.STORAGE_GCP_PROJECT = "testproject"
        mock_settings.STORAGE_GCP_PREFIX = "testprefix"

        from airweave.platform.storage.factory import get_storage_backend

        backend = get_storage_backend()

        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        assert isinstance(backend, GCSBackend)
        assert backend.bucket_name == "testbucket"
        assert backend.project == "testproject"
        assert backend.prefix == "testprefix/"

    @patch("airweave.platform.storage.factory.settings")
    def test_gcs_backend_requires_bucket(self, mock_settings):
        """Test factory raises error when GCS bucket is missing."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.GCP
        mock_settings.STORAGE_GCP_BUCKET = None

        from airweave.platform.storage.factory import get_storage_backend

        with pytest.raises(ValueError) as exc_info:
            get_storage_backend()

        assert "STORAGE_GCP_BUCKET" in str(exc_info.value)

    @patch("airweave.platform.storage.factory.settings")
    def test_unknown_backend_raises(self, mock_settings):
        """Test factory raises error for unknown backend type."""
        mock_settings.STORAGE_BACKEND = "unknown_backend"

        from airweave.platform.storage.factory import get_storage_backend

        with pytest.raises(ValueError) as exc_info:
            get_storage_backend()

        assert "Unknown STORAGE_BACKEND" in str(exc_info.value)

    @patch("airweave.platform.storage.factory.settings")
    def test_factory_caches_result(self, mock_settings, tmp_path):
        """Test that factory returns cached singleton."""
        mock_settings.STORAGE_BACKEND = StorageBackendType.FILESYSTEM
        mock_settings.STORAGE_PATH = str(tmp_path)

        from airweave.platform.storage.factory import get_storage_backend

        backend1 = get_storage_backend()
        backend2 = get_storage_backend()

        assert backend1 is backend2


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
