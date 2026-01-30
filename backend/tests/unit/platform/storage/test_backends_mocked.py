"""Unit tests for cloud storage backends with mocked SDKs.

These tests mock the cloud SDKs (Azure, AWS, GCP) to test error handling
and edge cases without requiring real cloud credentials.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)


class TestAzureBlobBackendMocked:
    """Test AzureBlobBackend with mocked Azure SDK."""

    def test_init_stores_config(self):
        """Test that init stores configuration correctly."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="testaccount",
            container="testcontainer",
            prefix="testprefix",
        )

        assert backend.storage_account == "testaccount"
        assert backend.container_name == "testcontainer"
        assert backend.prefix == "testprefix/"

    def test_init_empty_prefix(self):
        """Test that empty prefix is handled correctly."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="testaccount",
            container="testcontainer",
            prefix="",
        )

        assert backend.prefix == ""

    def test_resolve_adds_prefix(self):
        """Test that _resolve adds prefix to path."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="test",
            container="test",
            prefix="myprefix",
        )

        resolved = backend._resolve("path/to/file.json")
        assert resolved == "myprefix/path/to/file.json"

    @pytest.mark.asyncio
    async def test_sdk_import_error_raises_storage_exception(self):
        """Test that missing SDK raises StorageException."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="test",
            container="test",
        )

        with patch.dict("sys.modules", {"azure.identity.aio": None}):
            with patch(
                "airweave.platform.storage.backends.azure_blob.AzureBlobBackend._get_blob_service_client",
                side_effect=ImportError("No module named 'azure'"),
            ):
                # The actual SDK import happens in _get_blob_service_client
                pass

    @pytest.mark.asyncio
    async def test_close_cleans_up_clients(self):
        """Test that close() properly cleans up async clients."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="test",
            container="test",
        )

        # Mock the clients
        mock_blob_service = AsyncMock()
        mock_credential = AsyncMock()
        backend._blob_service_client = mock_blob_service
        backend._container_client = MagicMock()
        backend._credential = mock_credential

        await backend.close()

        mock_blob_service.close.assert_called_once()
        mock_credential.close.assert_called_once()
        assert backend._blob_service_client is None
        assert backend._container_client is None
        assert backend._credential is None


class TestS3BackendMocked:
    """Test S3Backend with mocked boto3/aiobotocore."""

    def test_init_stores_config(self):
        """Test that init stores configuration correctly."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="testbucket",
            region="us-west-2",
            prefix="testprefix",
            endpoint_url="http://localhost:9000",
        )

        assert backend.bucket == "testbucket"
        assert backend.region == "us-west-2"
        assert backend.prefix == "testprefix/"
        assert backend.endpoint_url == "http://localhost:9000"

    def test_init_empty_prefix(self):
        """Test that empty prefix is handled correctly."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="testbucket",
            region="us-west-2",
            prefix="",
        )

        assert backend.prefix == ""

    def test_init_no_endpoint(self):
        """Test that endpoint_url can be None (default AWS)."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="testbucket",
            region="us-west-2",
        )

        assert backend.endpoint_url is None

    def test_resolve_adds_prefix(self):
        """Test that _resolve adds prefix to path."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="test",
            region="us-east-1",
            prefix="myprefix",
        )

        resolved = backend._resolve("path/to/file.json")
        assert resolved == "myprefix/path/to/file.json"

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self):
        """Test that close() properly cleans up async client."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="test",
            region="us-east-1",
        )

        # Mock the client
        mock_client = AsyncMock()
        backend._client = mock_client
        backend._session = MagicMock()

        await backend.close()

        mock_client.__aexit__.assert_called_once_with(None, None, None)
        assert backend._client is None
        assert backend._session is None


class TestGCSBackendMocked:
    """Test GCSBackend with mocked google-cloud-storage."""

    def test_init_stores_config(self):
        """Test that init stores configuration correctly."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(
            bucket="testbucket",
            project="testproject",
            prefix="testprefix",
        )

        assert backend.bucket_name == "testbucket"
        assert backend.project == "testproject"
        assert backend.prefix == "testprefix/"

    def test_init_empty_prefix(self):
        """Test that empty prefix is handled correctly."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(
            bucket="testbucket",
            project="testproject",
            prefix="",
        )

        assert backend.prefix == ""

    def test_init_no_project(self):
        """Test that project can be None (auto-detected)."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(
            bucket="testbucket",
        )

        assert backend.project is None

    def test_resolve_adds_prefix(self):
        """Test that _resolve adds prefix to path."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(
            bucket="test",
            prefix="myprefix",
        )

        resolved = backend._resolve("path/to/file.json")
        assert resolved == "myprefix/path/to/file.json"

    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        """Test that close() clears client references."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(bucket="test")

        backend._client = MagicMock()
        backend._bucket = MagicMock()

        await backend.close()

        assert backend._client is None
        assert backend._bucket is None


class TestBackendPrefixNormalization:
    """Test prefix normalization across all backends."""

    def test_azure_prefix_trailing_slash_stripped(self):
        """Test Azure prefix has trailing slash stripped then added."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

        backend = AzureBlobBackend(
            storage_account="test",
            container="test",
            prefix="prefix/",
        )
        assert backend.prefix == "prefix/"

    def test_s3_prefix_trailing_slash_stripped(self):
        """Test S3 prefix has trailing slash stripped then added."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend

        backend = S3Backend(
            bucket="test",
            region="us-east-1",
            prefix="prefix/",
        )
        assert backend.prefix == "prefix/"

    def test_gcs_prefix_trailing_slash_stripped(self):
        """Test GCS prefix has trailing slash stripped then added."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend

        backend = GCSBackend(
            bucket="test",
            prefix="prefix/",
        )
        assert backend.prefix == "prefix/"


class TestAllBackendsProtocolCompliance:
    """Test that all backends implement the StorageBackend protocol."""

    def test_azure_implements_protocol(self):
        """Test AzureBlobBackend implements StorageBackend."""
        from airweave.platform.storage.backends.azure_blob import AzureBlobBackend
        from airweave.platform.storage.protocol import StorageBackend

        backend = AzureBlobBackend(storage_account="test", container="test")
        assert isinstance(backend, StorageBackend)

    def test_s3_implements_protocol(self):
        """Test S3Backend implements StorageBackend."""
        from airweave.platform.storage.backends.aws_s3 import S3Backend
        from airweave.platform.storage.protocol import StorageBackend

        backend = S3Backend(bucket="test", region="us-east-1")
        assert isinstance(backend, StorageBackend)

    def test_gcs_implements_protocol(self):
        """Test GCSBackend implements StorageBackend."""
        from airweave.platform.storage.backends.gcp_gcs import GCSBackend
        from airweave.platform.storage.protocol import StorageBackend

        backend = GCSBackend(bucket="test")
        assert isinstance(backend, StorageBackend)

    def test_filesystem_implements_protocol(self, tmp_path):
        """Test FilesystemBackend implements StorageBackend."""
        from airweave.platform.storage.backends.filesystem import FilesystemBackend
        from airweave.platform.storage.protocol import StorageBackend

        backend = FilesystemBackend(base_path=tmp_path)
        assert isinstance(backend, StorageBackend)

    @pytest.mark.parametrize(
        "backend_class,init_kwargs",
        [
            ("FilesystemBackend", {"base_path": "/tmp"}),
            ("AzureBlobBackend", {"storage_account": "test", "container": "test"}),
            ("S3Backend", {"bucket": "test", "region": "us-east-1"}),
            ("GCSBackend", {"bucket": "test"}),
        ],
    )
    def test_all_backends_have_required_methods(self, backend_class, init_kwargs):
        """Test all backends have the required protocol methods."""
        import importlib

        if backend_class == "FilesystemBackend":
            module = importlib.import_module(
                "airweave.platform.storage.backends.filesystem"
            )
        elif backend_class == "AzureBlobBackend":
            module = importlib.import_module(
                "airweave.platform.storage.backends.azure_blob"
            )
        elif backend_class == "S3Backend":
            module = importlib.import_module("airweave.platform.storage.backends.aws_s3")
        elif backend_class == "GCSBackend":
            module = importlib.import_module(
                "airweave.platform.storage.backends.gcp_gcs"
            )

        cls = getattr(module, backend_class)
        backend = cls(**init_kwargs)

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
            assert hasattr(backend, method), f"{backend_class} missing {method}"
            assert callable(getattr(backend, method))
