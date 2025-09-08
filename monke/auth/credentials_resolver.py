"""Centralized credential resolution for connectors.

Priority:
1) Explicit auth_fields provided in test config
2) Auth broker (e.g., Composio) if configured
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from monke.auth.broker import BaseAuthBroker, ComposioBroker


def _make_broker(source_short_name: str) -> Optional[BaseAuthBroker]:
    provider = os.getenv("DM_AUTH_PROVIDER")  # e.g., "composio"
    if not provider:
        return None
    if provider == "composio":
        # Check for source-specific account/config IDs
        source_upper = source_short_name.upper()
        account_id = os.getenv(f"{source_upper}_AUTH_PROVIDER_ACCOUNT_ID")
        auth_config_id = os.getenv(f"{source_upper}_AUTH_PROVIDER_AUTH_CONFIG_ID")

        # If source-specific IDs exist, use them
        if account_id and auth_config_id:
            return ComposioBroker(account_id=account_id, auth_config_id=auth_config_id)
        # Otherwise use default broker
        return ComposioBroker()
    raise ValueError(f"Unsupported auth provider: {provider}")


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

    broker = _make_broker(connector_short_name)

    if broker:
        return await broker.get_credentials(connector_short_name)

    raise ValueError(
        f"No credentials provided and no DM_AUTH_PROVIDER configured for {connector_short_name}"
    )
