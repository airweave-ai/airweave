"""Shared fixtures for storage backend integration tests.

These fixtures provide:
- Unique test prefixes for isolation
- Backend instances configured for test infrastructure
- Automatic cleanup after tests
"""

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio


@pytest.fixture
def storage_not_found_error():
    """Provide the StorageNotFoundError class for tests.

    Import lazily to avoid triggering the full airweave import chain
    (which requires env vars like POSTGRES_HOST to be set).
    """
    from airweave.platform.storage.exceptions import StorageNotFoundError

    return StorageNotFoundError

# Test infrastructure configuration (Airweave internal)
TEST_AWS_BUCKET = "airweave-storage-backend-tests"
TEST_AWS_REGION = "us-east-1"
TEST_GCP_BUCKET = "airweave-storage-backend-tests"
TEST_GCP_PROJECT = "airweave-production"
TEST_AZURE_ACCOUNT = "airweavecoredevstorage"
TEST_AZURE_CONTAINER = "backend-tests"


@pytest.fixture
def test_prefix() -> str:
    """Generate a unique prefix for test isolation.

    Each test gets its own prefix to avoid conflicts when running
    tests in parallel or when cleanup fails.
    """
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_data() -> dict:
    """Sample JSON data for testing."""
    return {
        "name": "test-entity",
        "count": 42,
        "nested": {"key": "value", "list": [1, 2, 3]},
        "unicode": "こんにちは世界",
    }


@pytest.fixture
def test_binary() -> bytes:
    """Sample binary data for testing."""
    return b"\x00\x01\x02\x03\x04\x05" + b"binary content" + bytes(range(256))


@pytest.fixture
def large_binary() -> bytes:
    """Large binary data (>1MB) for testing."""
    return b"x" * (1024 * 1024 + 1)  # 1MB + 1 byte


# =============================================================================
# Filesystem Backend Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def filesystem_backend(tmp_path, test_prefix) -> AsyncGenerator:
    """Create a FilesystemBackend for testing."""
    from airweave.platform.storage.backends.filesystem import FilesystemBackend

    backend = FilesystemBackend(base_path=tmp_path)
    yield backend
    # Cleanup is automatic since we use tmp_path


# =============================================================================
# Azure Blob Backend Fixtures
# =============================================================================


def azure_credentials_available() -> bool:
    """Check if Azure credentials are available."""
    try:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        # Try to get a token - this will fail fast if no credentials
        credential.get_token("https://storage.azure.com/.default")
        return True
    except Exception:
        return False


requires_azure = pytest.mark.skipif(
    not azure_credentials_available(),
    reason="Azure credentials not available",
)

# Composite marker for live cloud tests
live_azure = pytest.mark.usefixtures()  # Combines with requires_azure in test classes


@pytest_asyncio.fixture
async def azure_backend(test_prefix) -> AsyncGenerator:
    """Create an AzureBlobBackend for testing."""
    from airweave.platform.storage.backends.azure_blob import AzureBlobBackend

    backend = AzureBlobBackend(
        storage_account=TEST_AZURE_ACCOUNT,
        container=TEST_AZURE_CONTAINER,
        prefix=test_prefix,
    )
    yield backend
    # Cleanup: delete all test data
    try:
        await backend.delete("")
    except Exception:
        pass
    await backend.close()


# =============================================================================
# AWS S3 Backend Fixtures
# =============================================================================


def aws_credentials_available() -> bool:
    """Check if AWS credentials are available."""
    try:
        import boto3

        sts = boto3.client("sts")
        sts.get_caller_identity()
        return True
    except Exception:
        return False


requires_aws = pytest.mark.skipif(
    not aws_credentials_available(),
    reason="AWS credentials not available",
)

# Composite marker for live cloud tests
live_aws = pytest.mark.usefixtures()  # Combines with requires_aws in test classes


@pytest_asyncio.fixture
async def s3_backend(test_prefix) -> AsyncGenerator:
    """Create an S3Backend for testing."""
    from airweave.platform.storage.backends.aws_s3 import S3Backend

    backend = S3Backend(
        bucket=TEST_AWS_BUCKET,
        region=TEST_AWS_REGION,
        prefix=test_prefix,
    )
    yield backend
    # Cleanup: delete all test data
    try:
        await backend.delete("")
    except Exception:
        pass
    await backend.close()


# =============================================================================
# GCP GCS Backend Fixtures
# =============================================================================


def gcp_credentials_available() -> bool:
    """Check if GCP credentials are available."""
    try:
        from google.auth import default

        credentials, project = default()
        return True
    except Exception:
        return False


requires_gcp = pytest.mark.skipif(
    not gcp_credentials_available(),
    reason="GCP credentials not available",
)

# Composite marker for live cloud tests
live_gcp = pytest.mark.usefixtures()  # Combines with requires_gcp in test classes


@pytest_asyncio.fixture
async def gcs_backend(test_prefix) -> AsyncGenerator:
    """Create a GCSBackend for testing."""
    from airweave.platform.storage.backends.gcp_gcs import GCSBackend

    backend = GCSBackend(
        bucket=TEST_GCP_BUCKET,
        project=TEST_GCP_PROJECT,
        prefix=test_prefix,
    )
    yield backend
    # Cleanup: delete all test data
    try:
        await backend.delete("")
    except Exception:
        pass
    await backend.close()
