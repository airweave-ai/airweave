"""Domain types for the Connect module."""

from typing import FrozenSet

from airweave.schemas.connect_session import ConnectSessionMode

MODES_VIEW: FrozenSet[ConnectSessionMode] = frozenset(
    {ConnectSessionMode.ALL, ConnectSessionMode.MANAGE, ConnectSessionMode.REAUTH}
)
MODES_CREATE: FrozenSet[ConnectSessionMode] = frozenset(
    {ConnectSessionMode.ALL, ConnectSessionMode.CONNECT}
)
MODES_DELETE: FrozenSet[ConnectSessionMode] = frozenset(
    {ConnectSessionMode.ALL, ConnectSessionMode.MANAGE}
)

SSE_HEARTBEAT_INTERVAL_SECONDS = 30
