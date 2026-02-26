"""Root conftest for pytest configuration and shared fixtures.

This conftest is loaded before both testpaths (tests/ and airweave/domains/),
making its fixtures available to centralized tests AND colocated domain tests.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from airweave.adapters.metrics import (
        FakeAgenticSearchMetrics,
        FakeDbPoolMetrics,
        FakeHttpMetrics,
    )
    from airweave.core.fakes.metrics_service import FakeMetricsService
    from airweave.core.health.fakes import FakeHealthService

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
def fake_endpoint_verifier():
    """Fake EndpointVerifier that records verification calls."""
    from airweave.adapters.webhooks.fake import FakeEndpointVerifier

    return FakeEndpointVerifier()


@pytest.fixture
def fake_webhook_service():
    """Fake WebhookService with in-memory state for assertions."""
    from airweave.adapters.webhooks.fake import FakeWebhookService

    return FakeWebhookService()


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
def fake_http_metrics() -> FakeHttpMetrics:
    """Fake HttpMetrics that records calls in memory."""
    from airweave.adapters.metrics import FakeHttpMetrics

    return FakeHttpMetrics()


@pytest.fixture
def fake_agentic_search_metrics() -> FakeAgenticSearchMetrics:
    """Fake AgenticSearchMetrics that records calls in memory."""
    from airweave.adapters.metrics import FakeAgenticSearchMetrics

    return FakeAgenticSearchMetrics()


@pytest.fixture
def fake_db_pool_metrics() -> FakeDbPoolMetrics:
    """Fake DbPoolMetrics that records the latest update in memory."""
    from airweave.adapters.metrics import FakeDbPoolMetrics

    return FakeDbPoolMetrics()


@pytest.fixture
def fake_source_service():
    """Fake SourceService that returns canned source schemas."""
    from airweave.domains.sources.fakes.service import FakeSourceService

    return FakeSourceService()


@pytest.fixture
def fake_source_registry():
    """Fake SourceRegistry for testing registry consumers."""
    from airweave.domains.sources.fakes.registry import FakeSourceRegistry

    return FakeSourceRegistry()


@pytest.fixture
def fake_auth_provider_registry():
    """Fake AuthProviderRegistry for testing registry consumers."""
    from airweave.domains.auth_provider.fake import FakeAuthProviderRegistry

    return FakeAuthProviderRegistry()


@pytest.fixture
def fake_entity_definition_registry():
    """Fake EntityDefinitionRegistry for testing registry consumers."""
    from airweave.domains.entities.fakes.registry import FakeEntityDefinitionRegistry

    return FakeEntityDefinitionRegistry()


@pytest.fixture
def fake_metrics_service(
    fake_http_metrics,
    fake_agentic_search_metrics,
    fake_db_pool_metrics,
) -> FakeMetricsService:
    """FakeMetricsService wrapping individual metric fakes."""
    from airweave.core.fakes.metrics_service import FakeMetricsService

    return FakeMetricsService(
        http=fake_http_metrics,
        agentic_search=fake_agentic_search_metrics,
        db_pool=fake_db_pool_metrics,
    )


# ---------------------------------------------------------------------------
# Test container — fully faked Container for injection
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_health_service() -> FakeHealthService:
    """Fake HealthService with canned responses."""
    from airweave.core.health.fakes import FakeHealthService

    return FakeHealthService()


@pytest.fixture
def fake_source_connection_service(fake_sync_lifecycle):
    """Fake SourceConnectionService."""
    from airweave.domains.source_connections.fakes.service import FakeSourceConnectionService

    return FakeSourceConnectionService(sync_lifecycle=fake_sync_lifecycle)


@pytest.fixture
def fake_source_lifecycle_service():
    """Fake SourceLifecycleService for testing lifecycle consumers."""
    from airweave.domains.sources.fakes.lifecycle import FakeSourceLifecycleService

    return FakeSourceLifecycleService()


@pytest.fixture
def fake_sc_repo():
    """Fake SourceConnectionRepository."""
    from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository

    return FakeSourceConnectionRepository()


@pytest.fixture
def fake_conn_repo():
    """Fake ConnectionRepository."""
    from airweave.domains.connections.fakes.repository import FakeConnectionRepository

    return FakeConnectionRepository()


@pytest.fixture
def fake_collection_repo():
    """Fake CollectionRepository."""
    from airweave.domains.collections.fakes.repository import FakeCollectionRepository

    return FakeCollectionRepository()


@pytest.fixture
def fake_cred_repo():
    """Fake IntegrationCredentialRepository."""
    from airweave.domains.credentials.fakes.repository import FakeIntegrationCredentialRepository

    return FakeIntegrationCredentialRepository()


@pytest.fixture
def fake_oauth2_service():
    """Fake OAuth2Service."""
    from airweave.domains.oauth.fakes.oauth2_service import FakeOAuth2Service

    return FakeOAuth2Service()


@pytest.fixture
def fake_oauth1_service():
    """Real OAuth1Service (no injected deps, safe for unit tests)."""
    from airweave.domains.oauth.oauth1_service import OAuth1Service

    return OAuth1Service()


@pytest.fixture
def fake_redirect_session_repo():
    """Fake OAuthRedirectSessionRepository."""
    from airweave.domains.oauth.fakes.repository import FakeOAuthRedirectSessionRepository

    return FakeOAuthRedirectSessionRepository()


@pytest.fixture
def fake_response_builder():
    """Fake ResponseBuilder."""
    from airweave.domains.source_connections.fakes.response import FakeResponseBuilder

    return FakeResponseBuilder()


@pytest.fixture
def fake_temporal_workflow_service():
    """Fake TemporalWorkflowService."""
    from airweave.domains.temporal.fakes.service import FakeTemporalWorkflowService

    return FakeTemporalWorkflowService()


@pytest.fixture
def fake_temporal_schedule_service():
    """Fake TemporalScheduleService."""
    from airweave.domains.temporal.fakes.schedule_service import FakeTemporalScheduleService

    return FakeTemporalScheduleService()


@pytest.fixture
def fake_sync_repo():
    """Fake SyncRepository."""
    from airweave.domains.syncs.fakes.sync_repository import FakeSyncRepository

    return FakeSyncRepository()


@pytest.fixture
def fake_sync_cursor_repo():
    """Fake SyncCursorRepository."""
    from airweave.domains.syncs.fakes.sync_cursor_repository import FakeSyncCursorRepository

    return FakeSyncCursorRepository()


@pytest.fixture
def fake_sync_job_repo():
    """Fake SyncJobRepository."""
    from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository

    return FakeSyncJobRepository()


@pytest.fixture
def fake_billing_service():
    """Fake BillingService."""
    from airweave.adapters.payment.fake import FakePaymentGateway
    from airweave.domains.billing.fakes.operations import FakeBillingOperations
    from airweave.domains.billing.fakes.repository import (
        FakeBillingPeriodRepository,
        FakeOrganizationBillingRepository,
    )
    from airweave.domains.billing.service import BillingService
    from airweave.domains.organizations.fakes.repository import FakeOrganizationRepository

    return BillingService(
        payment_gateway=FakePaymentGateway(),
        billing_repo=FakeOrganizationBillingRepository(),
        period_repo=FakeBillingPeriodRepository(),
        billing_ops=FakeBillingOperations(),
        org_repo=FakeOrganizationRepository(),
    )


@pytest.fixture
def fake_sync_record_service():
    """Fake SyncRecordService."""
    from airweave.domains.syncs.fakes.sync_record_service import FakeSyncRecordService

    return FakeSyncRecordService()


@pytest.fixture
def fake_sync_job_service():
    """Fake SyncJobService."""
    from airweave.domains.syncs.fakes.sync_job_service import FakeSyncJobService

    return FakeSyncJobService()


@pytest.fixture
def fake_sync_lifecycle():
    """Fake SyncLifecycleService."""
    from airweave.domains.syncs.fakes.sync_lifecycle_service import FakeSyncLifecycleService

    return FakeSyncLifecycleService()


@pytest.fixture
def fake_billing_webhook():
    """Fake BillingWebhookProcessor."""
    from airweave.adapters.payment.fake import FakePaymentGateway
    from airweave.domains.billing.fakes.operations import FakeBillingOperations
    from airweave.domains.billing.fakes.repository import (
        FakeBillingPeriodRepository,
        FakeOrganizationBillingRepository,
    )
    from airweave.domains.billing.webhook_processor import BillingWebhookProcessor
    from airweave.domains.organizations.fakes.repository import FakeOrganizationRepository

    return BillingWebhookProcessor(
        payment_gateway=FakePaymentGateway(),
        billing_repo=FakeOrganizationBillingRepository(),
        period_repo=FakeBillingPeriodRepository(),
        billing_ops=FakeBillingOperations(),
        org_repo=FakeOrganizationRepository(),
    )


@pytest.fixture
def fake_payment_gateway():
    """Fake PaymentGateway."""
    from airweave.adapters.payment.fake import FakePaymentGateway

    return FakePaymentGateway()


@pytest.fixture
def fake_collection_service():
    """Fake CollectionService."""
    from airweave.domains.collections.fakes.service import FakeCollectionService

    return FakeCollectionService()


@pytest.fixture
def fake_oauth_flow_service():
    """Fake OAuthFlowService."""
    from airweave.domains.oauth.fakes.flow_service import FakeOAuthFlowService

    return FakeOAuthFlowService()


@pytest.fixture
def fake_oauth_callback_service():
    """Fake OAuthCallbackService."""
    from airweave.domains.oauth.fakes.callback_service import FakeOAuthCallbackService

    return FakeOAuthCallbackService()


@pytest.fixture
def fake_init_session_repo():
    """Fake OAuthInitSessionRepository."""
    from airweave.domains.oauth.fakes.repository import FakeOAuthInitSessionRepository

    return FakeOAuthInitSessionRepository()


@pytest.fixture
def test_container(
    fake_health_service,
    fake_event_bus,
    fake_webhook_publisher,
    fake_webhook_admin,
    fake_circuit_breaker,
    fake_ocr_provider,
    fake_metrics_service,
    fake_source_service,
    fake_endpoint_verifier,
    fake_webhook_service,
    fake_source_registry,
    fake_auth_provider_registry,
    fake_sc_repo,
    fake_collection_repo,
    fake_conn_repo,
    fake_cred_repo,
    fake_oauth1_service,
    fake_oauth2_service,
    fake_redirect_session_repo,
    fake_oauth_flow_service,
    fake_oauth_callback_service,
    fake_init_session_repo,
    fake_source_connection_service,
    fake_source_lifecycle_service,
    fake_response_builder,
    fake_temporal_workflow_service,
    fake_temporal_schedule_service,
    fake_sync_repo,
    fake_sync_cursor_repo,
    fake_sync_job_repo,
    fake_sync_record_service,
    fake_sync_job_service,
    fake_sync_lifecycle,
    fake_billing_service,
    fake_billing_webhook,
    fake_payment_gateway,
    fake_collection_service,
):
    """A Container with all dependencies replaced by fakes.

    Use this when testing code that receives a Container or individual
    protocols via dependency injection.

    For partial overrides, use container.replace():
        real_bus_container = test_container.replace(event_bus=InMemoryEventBus())
    """
    from airweave.core.container import Container

    return Container(
        health=fake_health_service,
        event_bus=fake_event_bus,
        webhook_publisher=fake_webhook_publisher,
        webhook_admin=fake_webhook_admin,
        endpoint_verifier=fake_endpoint_verifier,
        webhook_service=fake_webhook_service,
        circuit_breaker=fake_circuit_breaker,
        ocr_provider=fake_ocr_provider,
        metrics=fake_metrics_service,
        source_service=fake_source_service,
        source_registry=fake_source_registry,
        auth_provider_registry=fake_auth_provider_registry,
        collection_service=fake_collection_service,
        sc_repo=fake_sc_repo,
        collection_repo=fake_collection_repo,
        conn_repo=fake_conn_repo,
        cred_repo=fake_cred_repo,
        oauth1_service=fake_oauth1_service,
        oauth2_service=fake_oauth2_service,
        redirect_session_repo=fake_redirect_session_repo,
        oauth_flow_service=fake_oauth_flow_service,
        oauth_callback_service=fake_oauth_callback_service,
        init_session_repo=fake_init_session_repo,
        source_connection_service=fake_source_connection_service,
        source_lifecycle_service=fake_source_lifecycle_service,
        response_builder=fake_response_builder,
        temporal_workflow_service=fake_temporal_workflow_service,
        temporal_schedule_service=fake_temporal_schedule_service,
        sync_repo=fake_sync_repo,
        sync_cursor_repo=fake_sync_cursor_repo,
        sync_job_repo=fake_sync_job_repo,
        sync_record_service=fake_sync_record_service,
        sync_job_service=fake_sync_job_service,
        sync_lifecycle=fake_sync_lifecycle,
        billing_service=fake_billing_service,
        billing_webhook=fake_billing_webhook,
        payment_gateway=fake_payment_gateway,
    )
