"""API test fixtures.

Provides an async HTTP client wired to the FastAPI app with the DI container
overridden to use fakes. Available to all colocated API tests under api/.

Pattern:
    1. Override get_container -> returns test_container (all fakes)
    2. Override get_context  -> returns a minimal fake ApiContext
    3. Test hits the endpoint, asserts on HTTP response + fake state
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from airweave.api.context import ApiContext
from airweave.api.deps import get_container, get_context
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.schemas.organization import Organization

TEST_ORG_ID = uuid4()
TEST_REQUEST_ID = "test-request-00000000"


def _make_fake_context() -> ApiContext:
    """Build a minimal ApiContext for API tests."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )
    return ApiContext(
        request_id=TEST_REQUEST_ID,
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={"test": True},
        logger=logger.with_context(request_id=TEST_REQUEST_ID),
    )


@pytest_asyncio.fixture
async def client(test_container):
    """Async HTTP client with faked DI container and auth context."""
    from airweave.main import app

    fake_ctx = _make_fake_context()

    app.dependency_overrides[get_container] = lambda: test_container
    app.dependency_overrides[get_context] = lambda: fake_ctx

    app.state.http_metrics = test_container.metrics.http

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
