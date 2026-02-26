"""Webhooks domain test fixtures.

Domain-specific fixtures for testing webhook subscribers and event routing.
Shared fixtures (fake_event_bus, fake_webhook_publisher, fake_webhook_admin,
test_container) are inherited from the root conftest.py.
"""

import pytest

from airweave.domains.webhooks.subscribers import WebhookEventSubscriber


@pytest.fixture
def subscriber(fake_webhook_publisher):
    """WebhookEventSubscriber wired to the shared fake publisher."""
    return WebhookEventSubscriber(publisher=fake_webhook_publisher)
