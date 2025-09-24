"""Centralized credential resolution for connectors.

Priority:
1) Explicit auth_fields provided in test config (direct auth)
2) Composio auth broker if API key is configured
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from monke.auth.broker import BaseAuthBroker, ComposioBroker


def _make_broker() -> Optional[BaseAuthBroker]:
    """Create a Composio broker if API key is available."""
    # Check if Composio API key exists
    if not os.getenv("COMPOSIO_API_KEY"):
        return None

    # Return a broker without specific account/auth config
    # These will be provided from the YAML config when needed
    return ComposioBroker()


async def resolve_credentials(
    connector_short_name: str, provided_auth_fields: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Resolve credentials for a connector.

    Args:
        connector_short_name: The short name of the connector (e.g., "asana").
        provided_auth_fields: Optional credentials provided in the test config.

    Returns:
        Dict of credentials for the connector.
    """
    if provided_auth_fields:
        return provided_auth_fields

    broker = _make_broker()

    if broker:
        return await broker.get_credentials(connector_short_name)

    raise ValueError(
        f"No credentials provided and no Composio API key configured for {connector_short_name}"
    )
