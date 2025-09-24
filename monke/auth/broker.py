"""Pluggable authentication brokers for resolving connector credentials.

This module defines a provider-agnostic interface (BaseAuthBroker) and a
Composio-backed implementation that can fetch credentials for any toolkit
by its short name/slug.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from monke.utils.logging import get_logger


class BaseAuthBroker(ABC):
    """Abstract interface for resolving credentials for a connector.

    Implementations can use any external auth provider, e.g., Composio.
    """

    @abstractmethod
    async def get_credentials(
        self, source_short_name: str, required_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Return credentials for the given source.

        Args:
            source_short_name: Connector short name (e.g., "asana", "github").
            required_fields: Optional list of fields to narrow the returned dict.

        Returns:
            Dictionary of credentials suitable for the connector.
        """


class ComposioBroker(BaseAuthBroker):
    """Auth broker that resolves credentials from Composio service key."""

    BASE_URL = "https://backend.composio.dev/api/v3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        auth_config_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> None:
        self.logger = get_logger("composio_broker")
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.auth_config_id = auth_config_id
        self.account_id = account_id

        if not self.api_key:
            raise ValueError("Missing Composio API key (COMPOSIO_API_KEY)")

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.BASE_URL}{path}",
                headers={"x-api-key": self.api_key},
                params=params,
                timeout=30.0,
            )
            r.raise_for_status()
            return r.json()

    async def get_credentials(
        self, source_short_name: str, required_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        # Default mapping: slug == short_name. If exceptions arise, we can internalize a mapping here.

        # composio removes _ , eg. google_drive becomes googledrive
        if "_" in source_short_name:
            slug = "".join(source_short_name.split("_"))
        else:
            slug = source_short_name

        accounts = (await self._get("/connected_accounts")).get("items", [])
        matching = [a for a in accounts if a.get("toolkit", {}).get("slug") == slug]

        if not matching:
            raise RuntimeError(f"No Composio connected accounts for slug '{slug}'")

        selected = None
        if self.auth_config_id and self.account_id:
            for a in matching:
                if (
                    a.get("auth_config", {}).get("id") == self.auth_config_id
                    and a.get("id") == self.account_id
                ):
                    selected = a
                    break
            if not selected:
                raise RuntimeError(
                    "No Composio account found for provided auth_config_id/account_id and slug '"
                    + slug
                    + "'"
                )
        else:
            selected = matching[0]

        creds = selected.get("state", {}).get("val") or {}

        # Log credential resolution safely without exposing sensitive data
        sensitive_fields = [
            k
            for k in creds.keys()
            if any(sensitive in k.lower() for sensitive in ["token", "key", "secret", "password"])
        ]
        non_sensitive_fields = [k for k in creds.keys() if k not in sensitive_fields]

        self.logger.info(
            f"Resolved credentials from Composio for slug='{slug}' - "
            f"Total fields: {len(creds)}, Sensitive: {len(sensitive_fields)}, "
            f"Non-sensitive: {non_sensitive_fields if non_sensitive_fields else 'none'}"
        )

        if required_fields:
            # Keep only required fields if specified, plus common tokens if present
            allowed = set(required_fields) | {
                "access_token",
                "token",
                "generic_api_key",
            }
            creds = {k: v for k, v in creds.items() if k in allowed}

        return creds
