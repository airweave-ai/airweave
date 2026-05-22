"""Unit tests for AuthInvalidationNotifier — dedupe, DB flip, publish."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.events.enums import SourceConnectionEventType
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.domains.source_connections.auth_invalidation import (
    DEDUPE_TTL_SECONDS,
    AuthInvalidationNotifier,
)

ORG_ID = uuid4()


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = ORG_ID
    return ctx


def _make_sc(*, short_name: str = "slack", is_authenticated: bool = True) -> MagicMock:
    sc = MagicMock()
    sc.id = uuid4()
    sc.short_name = short_name
    sc.readable_collection_id = "my-collection-abc"
    sc.is_authenticated = is_authenticated
    return sc


def _build_notifier(
    *,
    sc_repo: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
    redis: AsyncMock | None = None,
) -> tuple[AuthInvalidationNotifier, AsyncMock, AsyncMock, AsyncMock]:
    sc_repo = sc_repo or MagicMock()
    if not hasattr(sc_repo, "get") or not isinstance(sc_repo.get, AsyncMock):
        sc_repo.get = AsyncMock()
    if not hasattr(sc_repo, "update") or not isinstance(sc_repo.update, AsyncMock):
        sc_repo.update = AsyncMock()

    event_bus = event_bus or MagicMock()
    if not hasattr(event_bus, "publish") or not isinstance(event_bus.publish, AsyncMock):
        event_bus.publish = AsyncMock()

    redis = redis or MagicMock()
    if not hasattr(redis, "set") or not isinstance(redis.set, AsyncMock):
        redis.set = AsyncMock(return_value=True)

    notifier = AuthInvalidationNotifier(sc_repo=sc_repo, event_bus=event_bus, redis=redis)
    return notifier, sc_repo, event_bus, redis


@pytest.mark.asyncio
async def test_first_call_acquires_lock_flips_db_and_publishes():
    """The first notify() in the TTL window flips DB and publishes."""
    sc = _make_sc(is_authenticated=True)
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=sc)
    sc_repo.update = AsyncMock()
    notifier, sc_repo, event_bus, redis = _build_notifier(sc_repo=sc_repo)

    result = await notifier.notify(
        AsyncMock(), _make_ctx(), source_connection_id=sc.id, error_reason="invalid_auth"
    )

    assert result is True
    # Acquired the lock with the right TTL
    redis.set.assert_awaited_once()
    args, kwargs = redis.set.call_args
    assert args[0] == f"auth_invalidated:{sc.id}"
    assert kwargs == {"ex": DEDUPE_TTL_SECONDS, "nx": True}
    # Flipped DB
    sc_repo.update.assert_awaited_once()
    update_kwargs = sc_repo.update.call_args.kwargs
    assert update_kwargs["obj_in"] == {"is_authenticated": False}
    # Published the event
    event_bus.publish.assert_awaited_once()
    published = event_bus.publish.call_args.args[0]
    assert isinstance(published, SourceConnectionLifecycleEvent)
    assert published.event_type == SourceConnectionEventType.AUTH_INVALIDATED
    assert published.source_connection_id == sc.id
    assert published.source_type == "slack"
    assert published.collection_readable_id == "my-collection-abc"
    assert published.is_authenticated is False
    assert published.error_reason == "invalid_auth"


@pytest.mark.asyncio
async def test_second_call_within_ttl_is_dedupe_skipped():
    """Second notify() within TTL window does not flip DB or publish."""
    sc = _make_sc()
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=sc)
    sc_repo.update = AsyncMock()
    redis = MagicMock()
    # First call: lock acquired (truthy). Second call: not acquired (falsy).
    redis.set = AsyncMock(side_effect=[True, None])

    notifier, sc_repo, event_bus, redis = _build_notifier(sc_repo=sc_repo, redis=redis)

    first = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=sc.id)
    second = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=sc.id)

    assert first is True
    assert second is False
    # Only one DB flip + one publish, despite two notify() calls
    assert sc_repo.update.await_count == 1
    assert event_bus.publish.await_count == 1


@pytest.mark.asyncio
async def test_db_flip_skipped_when_already_unauthenticated():
    """Skip the DB write when is_authenticated is already False.

    Still publishes the event so re-detections get re-notified after TTL.
    """
    sc = _make_sc(is_authenticated=False)
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=sc)
    sc_repo.update = AsyncMock()
    notifier, sc_repo, event_bus, _ = _build_notifier(sc_repo=sc_repo)

    result = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=sc.id)

    assert result is True
    sc_repo.update.assert_not_awaited()
    event_bus.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_failure_fails_open_and_still_publishes():
    """Fail open on Redis errors instead of swallowing the signal.

    Proceed with DB flip + publish so the customer still gets notified.
    """
    sc = _make_sc()
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=sc)
    sc_repo.update = AsyncMock()
    redis = MagicMock()
    redis.set = AsyncMock(side_effect=RuntimeError("redis down"))
    notifier, sc_repo, event_bus, _ = _build_notifier(sc_repo=sc_repo, redis=redis)

    result = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=sc.id)

    assert result is True
    sc_repo.update.assert_awaited_once()
    event_bus.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_source_connection_returns_false_without_publishing():
    """Return False without publishing when the connection no longer exists.

    Handles the case where the connection was deleted between detection
    and notify(); we don't want to fabricate an event.
    """
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=None)
    sc_repo.update = AsyncMock()
    notifier, sc_repo, event_bus, _ = _build_notifier(sc_repo=sc_repo)

    result = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=uuid4())

    assert result is False
    sc_repo.update.assert_not_awaited()
    event_bus.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_failure_returns_false_but_does_not_raise():
    """Swallow publish failures so callers (search requests) don't 500.

    notify() returns False when publish raises, but the exception itself
    must not propagate to the caller.
    """
    sc = _make_sc()
    sc_repo = MagicMock()
    sc_repo.get = AsyncMock(return_value=sc)
    sc_repo.update = AsyncMock()
    event_bus = MagicMock()
    event_bus.publish = AsyncMock(side_effect=RuntimeError("bus down"))
    notifier, _, _, _ = _build_notifier(sc_repo=sc_repo, event_bus=event_bus)

    result = await notifier.notify(AsyncMock(), _make_ctx(), source_connection_id=sc.id)

    assert result is False  # publish failed, but no exception propagated
