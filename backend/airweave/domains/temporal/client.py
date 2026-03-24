"""Temporal client — module-level singleton with lazy connection."""

from __future__ import annotations

from temporalio.client import Client
from temporalio.runtime import Runtime

from airweave.core.config import settings
from airweave.core.logging import logger

_client: Client | None = None


async def get_client(*, runtime: Runtime | None = None) -> Client:
    """Return the cached Temporal client, connecting on first call.

    Args:
        runtime: Optional Temporal Runtime with telemetry configured.
                 The worker passes a Runtime with PrometheusConfig to
                 expose ``temporal_*`` SDK metrics; the API server
                 omits it so no metrics port is bound.
    """
    global _client
    if _client is None:
        logger.info(
            f"Connecting to Temporal at {settings.temporal_address}, "
            f"namespace: {settings.TEMPORAL_NAMESPACE}"
        )
        _client = await Client.connect(
            target_host=settings.temporal_address,
            namespace=settings.TEMPORAL_NAMESPACE,
            runtime=runtime,
        )
    return _client


async def close() -> None:
    """Release the cached client reference."""
    global _client
    _client = None


def get_cached_client() -> Client | None:
    """Return the cached client without connecting. Used by health probes."""
    return _client
