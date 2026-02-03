"""Integration tests for GCSBackend.

Tests run against real Google Cloud Storage:
- Bucket: airweave-storage-backend-tests
- Project: airweave-production

Requires GCP credentials (Application Default Credentials).
"""

import pytest
import pytest_asyncio

from .base_tests import BaseStorageBackendTests
from .conftest import requires_gcp

pytestmark = [pytest.mark.live_integration, requires_gcp]


@pytest_asyncio.fixture
async def backend(gcs_backend):
    """Provide the backend fixture for base tests."""
    return gcs_backend


class TestGCSBackend(BaseStorageBackendTests):
    """GCSBackend tests - inherits all tests from BaseStorageBackendTests."""

    pass
