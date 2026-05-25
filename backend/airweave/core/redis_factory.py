"""Redis client factory with Sentinel support.

Centralises Redis client construction so that both the main connection pool
(``core/redis_client.py``) and long-lived pubsub connections
(``adapters/pubsub/redis.py``) pick the same backend based on configuration.

Two modes are supported:

- **Single-host** (default): ``REDIS_HOST`` / ``REDIS_PORT`` are used directly.
- **Sentinel**: when ``REDIS_NODES`` and ``REDIS_SERVICE_NAME`` are both set,
  a ``redis.asyncio.sentinel.Sentinel`` instance is built from the node list
  and the current master is discovered via ``master_for(...)``. ``REDIS_HOST``
  and ``REDIS_PORT`` are ignored.
"""

from __future__ import annotations

import json
import platform
import socket
from typing import Any

import redis.asyncio as redis  # type: ignore[import-untyped]
from redis.asyncio.sentinel import Sentinel  # type: ignore[import-untyped]

from airweave.core.config import settings


def is_sentinel_mode() -> bool:
    """Return True when both ``REDIS_NODES`` and ``REDIS_SERVICE_NAME`` are set."""
    return bool(settings.REDIS_NODES) and bool(settings.REDIS_SERVICE_NAME)


def _parse_sentinel_nodes(raw: str) -> list[tuple[str, int]]:
    """Parse the ``REDIS_NODES`` JSON string into a list of ``(host, port)`` tuples."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"REDIS_NODES must be a JSON list of [host, port] pairs, got: {raw!r}"
        ) from exc

    if not isinstance(parsed, list) or not parsed:
        raise ValueError(
            f"REDIS_NODES must be a non-empty JSON list of [host, port] pairs, got: {raw!r}"
        )

    nodes: list[tuple[str, int]] = []
    for entry in parsed:
        if (
            not isinstance(entry, (list, tuple))
            or len(entry) != 2
            or not isinstance(entry[0], str)
            or not isinstance(entry[1], (int, str))
        ):
            raise ValueError(f"REDIS_NODES entries must be [host, port], got: {entry!r}")
        host, port = entry
        nodes.append((host, int(port)))
    return nodes


def get_socket_keepalive_options() -> dict[int, int]:
    """Return TCP keepalive options that work on the current OS.

    macOS does not support the Linux keepalive constants and will raise if they
    are passed to ``setsockopt``. We return an empty dict there and on any
    Linux system that does not expose ``TCP_KEEPIDLE``.
    """
    if platform.system() == "Darwin":
        return {}
    if not hasattr(socket, "TCP_KEEPIDLE"):
        return {}
    return {
        socket.TCP_KEEPIDLE: 60,
        socket.TCP_KEEPINTVL: 10,
        socket.TCP_KEEPCNT: 6,
    }


def make_redis_client(
    *,
    db: int | None = None,
    max_connections: int = 50,
    decode_responses: bool = True,
    **extra: Any,
) -> redis.Redis:
    """Build an async Redis client honouring the configured connection mode.

    Args:
        db: Database index. Defaults to ``settings.REDIS_DB``.
        max_connections: Connection pool size for both modes.
        decode_responses: Whether to decode responses to ``str``.
        **extra: Forwarded to the underlying ``Redis`` / ``ConnectionPool``
            constructor (e.g. ``socket_keepalive``, ``socket_timeout``,
            ``retry_on_error``).

    Returns:
        A connected (or lazily-connecting) ``redis.asyncio.Redis`` instance.
        In Sentinel mode the returned client transparently re-discovers the
        master after a failover.
    """
    if db is None:
        db = settings.REDIS_DB
    password = settings.REDIS_PASSWORD or None

    if is_sentinel_mode():
        assert settings.REDIS_NODES is not None
        assert settings.REDIS_SERVICE_NAME is not None
        nodes = _parse_sentinel_nodes(settings.REDIS_NODES)
        # Pull connection-tuning kwargs out of ``extra`` so we can forward them
        # to both the Sentinel itself (for sentinel-discovery RPCs) and to the
        # master pool that ``master_for`` builds.
        sentinel_kwargs = {
            "socket_connect_timeout": extra.get("socket_connect_timeout", 5),
            "socket_timeout": extra.get("socket_timeout", 5),
        }
        sentinel = Sentinel(
            nodes,
            password=password,
            **sentinel_kwargs,
        )
        return sentinel.master_for(
            settings.REDIS_SERVICE_NAME,
            db=db,
            password=password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            **extra,
        )

    pool = redis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=db,
        password=password,
        decode_responses=decode_responses,
        max_connections=max_connections,
        **extra,
    )
    return redis.Redis(connection_pool=pool)
