"""Root conftest for pytest configuration and shared fixtures.

This conftest is loaded before both testpaths (tests/ and airweave/domains/),
making its fixtures available to centralized tests AND colocated domain tests.
"""

import os

import pytest

# Register pytest-asyncio plugin at the root level
pytest_plugins = ("pytest_asyncio",)

# ---------------------------------------------------------------------------
# Environment variables — must be set before any airweave module import
# Uses setdefault so real env vars (CI, e2e) are never overridden.
# ---------------------------------------------------------------------------
os.environ.setdefault("FIRST_SUPERUSER", "test@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "testpassword123")
os.environ.setdefault("ENCRYPTION_KEY", "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0=")
os.environ.setdefault("STATE_SECRET", "test-state-secret-key-minimum-32-characters-long")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("AUTH_ENABLED", "false")


# ---------------------------------------------------------------------------
# Shared fake fixtures — individual protocol fakes
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_event_bus():
    """Fake EventBus that records published events."""
    from airweave.adapters.event_bus.fake import FakeEventBus

    return FakeEventBus()


@pytest.fixture
def fake_webhook_publisher():
    """Fake WebhookPublisher that records published events."""
    from airweave.adapters.webhooks.fake import FakeWebhookPublisher

    return FakeWebhookPublisher()


@pytest.fixture
def fake_webhook_admin():
    """Fake WebhookAdmin that records all operations."""
    from airweave.adapters.webhooks.fake import FakeWebhookAdmin

    return FakeWebhookAdmin()


@pytest.fixture
def fake_circuit_breaker():
    """Fake CircuitBreaker that tracks provider state."""
    from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker

    return FakeCircuitBreaker()


@pytest.fixture
def fake_ocr_provider():
    """Fake OcrProvider that returns canned markdown."""
    from airweave.adapters.ocr.fake import FakeOcrProvider

    return FakeOcrProvider()


@pytest.fixture
def fake_source_service():
    """Fake SourceService that returns canned source schemas."""
    from airweave.domains.sources.fake import FakeSourceService

    return FakeSourceService()


@pytest.fixture
def fake_source_registry():
    """Fake SourceRegistry for testing registry consumers."""
    from airweave.domains.sources.fake import FakeSourceRegistry

    return FakeSourceRegistry()


@pytest.fixture
def fake_auth_provider_registry():
    """Fake AuthProviderRegistry for testing registry consumers."""
    from airweave.domains.auth_provider.fake import FakeAuthProviderRegistry

    return FakeAuthProviderRegistry()


@pytest.fixture
def fake_entity_definition_registry():
    """Fake EntityDefinitionRegistry for testing registry consumers."""
    from airweave.domains.entities.fake import FakeEntityDefinitionRegistry

    return FakeEntityDefinitionRegistry()


# ---------------------------------------------------------------------------
# Test container — fully faked Container for injection
# ---------------------------------------------------------------------------


@pytest.fixture
def test_container(
    fake_event_bus,
    fake_webhook_publisher,
    fake_webhook_admin,
    fake_circuit_breaker,
    fake_ocr_provider,
    fake_source_service,
):
    """A Container with all dependencies replaced by fakes.

    Use this when testing code that receives a Container or individual
    protocols via dependency injection.

    For partial overrides, use container.replace():
        real_bus_container = test_container.replace(event_bus=InMemoryEventBus())
    """
    from airweave.core.container import Container

    return Container(
        event_bus=fake_event_bus,
        webhook_publisher=fake_webhook_publisher,
        webhook_admin=fake_webhook_admin,
        circuit_breaker=fake_circuit_breaker,
        ocr_provider=fake_ocr_provider,
        source_service=fake_source_service,
    )
