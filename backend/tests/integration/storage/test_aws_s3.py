"""Integration tests for S3Backend.

Tests run against real AWS S3:
- Bucket: airweave-storage-backend-tests
- Region: us-east-1

Requires AWS credentials (standard credential chain).
"""

import pytest
import pytest_asyncio

from .base_tests import BaseStorageBackendTests
from .conftest import requires_aws

pytestmark = [pytest.mark.live_integration, requires_aws]


@pytest_asyncio.fixture
async def backend(s3_backend):
    """Provide the backend fixture for base tests."""
    return s3_backend


class TestS3Backend(BaseStorageBackendTests):
    """S3Backend tests - inherits all tests from BaseStorageBackendTests."""

    pass
