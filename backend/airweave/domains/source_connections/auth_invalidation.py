"""Auth invalidation notifier.

Single entry-point for reporting that a source connection's credentials
were observed to be invalid at runtime. Handles three things atomically
per detection:

1. Per-connection Redis dedupe (1 h TTL) so a single broken connection
   doesn't spam customers' webhooks once per search.
2. Flipping ``is_authenticated=False`` on the source connection row so the
   UI immediately shows the connection as needing re-auth (instead of
   waiting for the next sync to record the failure).
3. Publishing a ``SourceConnectionLifecycleEvent.auth_invalidated`` event,
   which the webhook subscriber forwards to customer endpoints.

Callers (federated search, OAuth refresh failures, etc.) only need to call
``notify(...)``; everything else is internal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from airweave.api.context import ApiContext
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol

if TYPE_CHECKING:
    import redis.asyncio as redis  # type: ignore[import-untyped]
    from sqlalchemy.ext.asyncio import AsyncSession


# 1 hour dedupe window. Within this window we publish at most one
# AUTH_INVALIDATED webhook per source_connection_id. Picked to balance
# "don't spam customers" against "re-notify them if they ignore the first
# alert" — see the design discussion on PR #1795.
DEDUPE_TTL_SECONDS = 3600


class AuthInvalidationNotifier:
    """Idempotent emitter for AUTH_INVALIDATED events."""

    def __init__(
        self,
        *,
        sc_repo: SourceConnectionRepositoryProtocol,
        event_bus: EventBus,
        redis: "redis.Redis",
    ) -> None:
        """Initialize with deps. ``redis`` is the shared async Redis client."""
        self._sc_repo = sc_repo
        self._event_bus = event_bus
        self._redis = redis

    async def notify(
        self,
        db: "AsyncSession",
        ctx: ApiContext,
        *,
        source_connection_id: UUID,
        error_reason: Optional[str] = None,
    ) -> bool:
        """Record an auth invalidation for the given source connection.

        Returns ``True`` if this call won the dedupe race (DB flipped and
        webhook published), ``False`` if a previous call within the TTL
        window already handled this connection.

        Errors from Redis, the DB, or the event bus are logged but never
        re-raised — the calling search request must not fail because the
        notifier had trouble.
        """
        sc_id_str = str(source_connection_id)
        dedupe_key = f"auth_invalidated:{sc_id_str}"

        try:
            # SET NX EX — only succeeds if the key isn't set.
            # Returns truthy on first detection within the TTL window.
            acquired = await self._redis.set(dedupe_key, "1", ex=DEDUPE_TTL_SECONDS, nx=True)
        except Exception as exc:
            # Redis is down or misbehaving. Fail open: still flip DB +
            # publish so we never silently swallow the signal.
            logger.warning(
                f"AuthInvalidationNotifier: redis dedupe check failed for "
                f"{sc_id_str}: {exc}. Proceeding without dedupe."
            )
            acquired = True

        if not acquired:
            logger.debug(f"AuthInvalidationNotifier: dedupe hit for {sc_id_str}, skipping")
            return False

        try:
            sc = await self._sc_repo.get(db, source_connection_id, ctx)
        except Exception as exc:
            logger.exception(
                f"AuthInvalidationNotifier: failed to load source connection {sc_id_str}: {exc}"
            )
            return False

        if sc is None:
            logger.warning(
                f"AuthInvalidationNotifier: source connection {sc_id_str} not "
                f"found (likely deleted between detection and notify); skipping"
            )
            return False

        # Flip the DB flag if it isn't already off. Doing this here keeps
        # the UI's computed status (NEEDS_REAUTH) honest the moment we
        # detect bad auth, instead of waiting for the next sync job.
        if sc.is_authenticated:
            try:
                await self._sc_repo.update(
                    db, db_obj=sc, obj_in={"is_authenticated": False}, ctx=ctx
                )
            except Exception as exc:
                logger.exception(
                    f"AuthInvalidationNotifier: failed to flip is_authenticated "
                    f"for {sc_id_str}: {exc}"
                )

        # Publish the lifecycle event. The webhook subscriber forwards
        # this to customer-configured endpoints.
        try:
            await self._event_bus.publish(
                SourceConnectionLifecycleEvent.auth_invalidated(
                    organization_id=ctx.organization.id,
                    source_connection_id=source_connection_id,
                    source_type=str(sc.short_name),
                    collection_readable_id=str(sc.readable_collection_id or ""),
                    error_reason=error_reason,
                )
            )
        except Exception as exc:
            logger.exception(
                f"AuthInvalidationNotifier: event_bus.publish failed for {sc_id_str}: {exc}"
            )
            return False

        logger.info(
            f"AuthInvalidationNotifier: published AUTH_INVALIDATED for "
            f"connection={sc_id_str} reason={error_reason!r}"
        )
        return True
