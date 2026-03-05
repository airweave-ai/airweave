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
        self.api_key = api_key or os.getenv("MONKE_COMPOSIO_API_KEY")
        self.auth_config_id = auth_config_id
        self.account_id = account_id

        if not self.api_key:
            raise ValueError("Missing Composio API key (MONKE_COMPOSIO_API_KEY)")

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.BASE_URL}{path}",
                headers={"x-api-key": self.api_key},
                params=params,
                timeout=30.0,
            )
            r.raise_for_status()
            return r.json()

    async def _get_all_accounts(self) -> List[Dict[str, Any]]:
        """Fetch all connected accounts from Composio with pagination until exhaustion.

        Returns:
            List of all connected account dictionaries.
        """
        all_accounts = []
        page = 1
        page_size = 100

        while True:
            response = await self._get(
                "/connected_accounts", params={"limit": page_size, "page": page}
            )
            items = response.get("items", [])

            if not items:
                break

            all_accounts.extend(items)

            # Check if there are more pages
            # If we got fewer items than the page size, we've reached the end
            if len(items) < page_size:
                break

            page += 1

        self.logger.info(
            f"Fetched {len(all_accounts)} total connected accounts from Composio"
        )
        return all_accounts

    async def get_credentials(
        self, source_short_name: str, required_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        # Mapping of Airweave source short names to Composio toolkit slugs
        # This should match the SLUG_NAME_MAPPING in platform/auth_providers/composio.py
        SLUG_MAPPING = {
            "google_drive": "googledrive",
            "google_calendar": "googlecalendar",
            "google_slides": "googleslides",
            "outlook_mail": "outlook",
            "outlook_calendar": "outlook",
            "onedrive": "one_drive",
            "sharepoint": "one_drive",  # this is not a bug, we are using the one drive token for sharepoint given overlapping scopes
            "teams": "microsoft_teams",
            "onenote": "one_drive",  # OneNote uses OneDrive integration (same Graph API)
            "word": "one_drive",  # Word uses OneDrive integration (same Graph API)
            "powerpoint": "one_drive",  # PowerPoint uses OneDrive integration (same Graph API)
        }

        # Check if we have an explicit mapping
        if source_short_name in SLUG_MAPPING:
            slug = SLUG_MAPPING[source_short_name]
        # Otherwise, use default logic: composio removes underscores
        elif "_" in source_short_name:
            slug = "".join(source_short_name.split("_"))
        else:
            slug = source_short_name

        accounts = await self._get_all_accounts()
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
            if any(
                sensitive in k.lower()
                for sensitive in ["token", "key", "secret", "password"]
            )
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
