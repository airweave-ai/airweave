"""Protocol injection for FastAPI endpoints."""

from typing import get_type_hints

from fastapi import Depends

from airweave.core import container
from airweave.core.container import Container

# Cache of protocol_type → Container field name, built once at first call.
_INJECT_CACHE: dict[type, str] = {}


def _resolve_field_name(protocol_type: type) -> str:
    """Find which Container field matches the given protocol type.

    Uses get_type_hints() to introspect the Container dataclass.
    Result is cached so the lookup happens at most once per protocol type.
    """
    if not _INJECT_CACHE:
        # Populate cache on first call
        for name, hint in get_type_hints(Container).items():
            _INJECT_CACHE[hint] = name

    field_name = _INJECT_CACHE.get(protocol_type)
    if field_name is None:
        available = list(_INJECT_CACHE.values())
        raise TypeError(
            f"No binding for {protocol_type.__name__} in Container. Available fields: {available}"
        )
    return field_name


def Inject(protocol_type: type):  # noqa: N802 — uppercase to match FastAPI convention
    """Resolve a protocol implementation from the DI container.

    Works like ``Depends()`` but looks up the implementation by protocol type
    instead of requiring the caller to know about the Container internals.

    Usage in FastAPI endpoints::

        from airweave.api.deps import Inject
        from airweave.core.protocols import EventBus, WebhookAdmin


        @router.post("/")
        async def create(
            event_bus: EventBus = Inject(EventBus),
            webhook_admin: WebhookAdmin = Inject(WebhookAdmin),
        ):
            await event_bus.publish(...)
    """
    field_name = _resolve_field_name(protocol_type)

    def _resolve_container():
        return container

    def _resolve(c: Container = Depends(_resolve_container)):
        return getattr(c, field_name)

    return Depends(_resolve)
