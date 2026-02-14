"""Core protocols for dependency injection."""

from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.collection import CollectionRepositoryProtocol
from airweave.core.protocols.connection import ConnectionRepositoryProtocol
from airweave.core.protocols.credential import CredentialServiceProtocol
from airweave.core.protocols.entity_count import EntityCountRepositoryProtocol
from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler
from airweave.core.protocols.integration_credential_repository import (
    IntegrationCredentialRepositoryProtocol,
)
from airweave.core.protocols.oauth import OAuthFlowServiceProtocol
from airweave.core.protocols.ocr import OcrProvider
from airweave.core.protocols.sync import SyncRepositoryProtocol
from airweave.core.protocols.sync_cursor import SyncCursorRepositoryProtocol
from airweave.core.protocols.sync_job import SyncJobRepositoryProtocol
from airweave.core.protocols.webhooks import WebhookAdmin, WebhookPublisher

__all__ = [
    "CircuitBreaker",
    "CollectionRepositoryProtocol",
    "ConnectionRepositoryProtocol",
    "CredentialServiceProtocol",
    "DomainEvent",
    "EntityCountRepositoryProtocol",
    "EventBus",
    "EventHandler",
    "IntegrationCredentialRepositoryProtocol",
    "OAuthFlowServiceProtocol",
    "OcrProvider",
    "SyncCursorRepositoryProtocol",
    "SyncJobRepositoryProtocol",
    "SyncRepositoryProtocol",
    "WebhookAdmin",
    "WebhookPublisher",
]
