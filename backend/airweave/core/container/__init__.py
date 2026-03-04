"""Dependency Injection Container Module.

This module provides the DI container and factory for wiring dependencies
across the application.

Usage:
------
    # Initialize at startup (call once from main.py or worker.py)
    from airweave.core.container import initialize_container
    from airweave.core.config import settings
    initialize_container(settings)

    # Import the global container after initialization
    from airweave.core.container import container
    store = container.event_message_store

    # In FastAPI deps.py
    def get_container() -> Container:
        return container

    # In Temporal worker.py
    activities = [
        RunSyncActivity(webhook_publisher=container.webhook_publisher),
    ]

    # In tests (construct directly with fakes, don't use global)
    from airweave.core.container import Container
    test_container = Container(
        event_bus=FakeEventBus(),
        webhook_publisher=FakeWebhookPublisher(),
        webhook_admin=FakeWebhookAdmin(),
        endpoint_verifier=FakeEndpointVerifier(),
        webhook_service=FakeWebhookService(),
        metrics=FakeMetricsService(),
    )

Module structure:
-----------------
    container/
    ├── __init__.py      # This file - exports public API
    ├── container.py     # Container dataclass (serves)
    └── factory.py       # create_container() (builds)
"""

from typing import TYPE_CHECKING

from airweave.core.container.container import Container
from airweave.core.container.factory import create_container

if TYPE_CHECKING:
    from airweave.core.config import Settings

__all__ = ["Container", "create_container", "container", "initialize_container"]


# ---------------------------------------------------------------------------
# Global container instance
# ---------------------------------------------------------------------------

container: Container | None = None
"""Global container instance.

Initialized via `initialize_container()` at application startup.

Import and use this in:
- api/deps.py: For FastAPI dependency functions
- platform/temporal/worker/wiring.py: For Temporal activity construction

Do NOT import this in domain code. Domains receive dependencies
via function parameters, never by importing the container directly.
"""


def initialize_container(settings: "Settings") -> None:
    """Initialize the global container. Call once at startup.

    This must be called before any code attempts to use the container.
    Typically called from:
    - main.py lifespan (FastAPI)
    - worker.py main() (Temporal)

    Args:
        settings: Application settings from core/config.py

    Raises:
        RuntimeError: If called more than once (container already initialized)

    Example:
    --------
        # In main.py lifespan
        from airweave.core.container import initialize_container
        from airweave.core.config import settings

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            initialize_container(settings)
    """
    global container

    if container is not None:
        raise RuntimeError(
            "Container already initialized. "
            "initialize_container() should only be called once at startup."
        )

    container = create_container(settings)


def reset_container() -> None:
    """Reset the global container to None. For testing only.

    This allows tests to reinitialize the container with different
    settings or to ensure a clean state between tests.

    WARNING: Do not use in production code.
    """
    global container
    container = None
