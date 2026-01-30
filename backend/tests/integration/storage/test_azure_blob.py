"""Integration tests for AzureBlobBackend.

Tests run against real Azure Blob Storage:
- Storage Account: airweavecoredevstorage
- Container: backend-tests

Requires Azure credentials (DefaultAzureCredential).
"""

import pytest
import pytest_asyncio

from .base_tests import BaseStorageBackendTests
from .conftest import requires_azure

pytestmark = [pytest.mark.live_integration, requires_azure]


@pytest_asyncio.fixture
async def backend(azure_backend):
    """Provide the backend fixture for base tests."""
    return azure_backend


class TestAzureBlobBackend(BaseStorageBackendTests):
    """AzureBlobBackend tests - inherits all tests from BaseStorageBackendTests."""

    pass
