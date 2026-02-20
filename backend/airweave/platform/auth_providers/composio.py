"""Composio Test Auth Provider - provides authentication services for other integrations."""

from typing import Any, Dict, List, Optional, Set

import httpx
from fastapi import HTTPException

from airweave.core.credential_sanitizer import (
    safe_log_credentials,
    sanitize_credentials_dict,
)
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.configs.auth import ComposioAuthConfig
from airweave.platform.configs.config import ComposioConfig
from airweave.platform.decorators import auth_provider


@auth_provider(
    name="Composio",
    short_name="composio",
    auth_config_class=ComposioAuthConfig,
    config_class=ComposioConfig,
)
class ComposioAuthProvider(BaseAuthProvider):
    """Composio authentication provider."""

    # Sources that Composio does not support
    BLOCKED_SOURCES = [
        "postgresql",
        "ctti",
        "sharepoint",
        "document360",
    ]

    # Mapping of Airweave field names to Composio field names
    # Key: Airweave field name, Value: Composio field name
    FIELD_NAME_MAPPING = {
        "api_key": "generic_api_key",  # Stripe and other API key sources
        "personal_access_token": "access_token",  # GitHub PAT mapping
        # Add more mappings as needed
    }

    # Mapping of Airweave source short names to Composio toolkit slugs
    # Key: Airweave short name, Value: Composio toolkit slug
    # Only include mappings where names differ between Airweave and Composio
    SLUG_NAME_MAPPING = {
        "google_drive": "googledrive",
        "google_calendar": "googlecalendar",
        "google_docs": "googledocs",
        "google_slides": "googleslides",
        "outlook_mail": "outlook",
        "outlook_calendar": "outlook",
        "onedrive": "one_drive",
        "sharepoint": "one_drive",  # Use OneDrive integration (same Graph API)
        "teams": "microsoft_teams",
        "onenote": "one_drive",
        "word": "one_drive",
        # Add more mappings as needed
    }

    @classmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "ComposioAuthProvider":
        """Create a new Composio auth provider instance.

        Args:
            credentials: Auth credentials containing api_key
            config: Configuration parameters

        Returns:
            A Composio test auth provider instance
        """
        instance = cls()
        instance.api_key = credentials["api_key"]
        instance.auth_config_id = config.get("auth_config_id")
        instance.account_id = config.get("account_id")
        instance._last_credential_blob = None
        return instance

    def _get_composio_slug(self, airweave_short_name: str) -> str:
        """Get the Composio toolkit slug for an Airweave source short name.

        Args:
            airweave_short_name: The Airweave source short name

        Returns:
            The corresponding Composio toolkit slug
        """
        return self.SLUG_NAME_MAPPING.get(airweave_short_name, airweave_short_name)

    def _map_field_name(self, airweave_field: str) -> str:
        """Map an Airweave field name to the corresponding Composio field name.

        Args:
            airweave_field: The Airweave field name

        Returns:
            The corresponding Composio field name
        """
        return self.FIELD_NAME_MAPPING.get(airweave_field, airweave_field)

    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated API request using Composio API key.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        headers = {"x-api-key": self.api_key}

        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Composio API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Composio API: {url}, {str(e)}")
            raise

    async def _get_all_connected_accounts(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Fetch all connected accounts from Composio with pagination until exhaustion.

        Args:
            client: HTTP client

        Returns:
            List of all connected account dictionaries
        """
        all_accounts = []
        page = 1
        page_size = 100

        while True:
            response = await self._get_with_auth(
                client,
                "https://backend.composio.dev/api/v3/connected_accounts",
                params={"limit": page_size, "page": page},
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
            f"📊 [Composio] Fetched {len(all_accounts)} total connected accounts from Composio"
        )
        return all_accounts

    async def get_creds_for_source(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get credentials for a specific source integration.

        Args:
            source_short_name: The short name of the source to get credentials for
            source_auth_config_fields: The fields required for the source auth config
            optional_fields: Fields that can be skipped if not available in Composio

        Returns:
            Credentials dictionary for the source

        Raises:
            HTTPException: If no credentials found for the source
        """
        # Map Airweave source name to Composio slug if needed
        composio_slug = self._get_composio_slug(source_short_name)

        self.logger.info(
            f"🔍 [Composio] Starting credential retrieval for source '{source_short_name}'"
        )
        if composio_slug != source_short_name:
            self.logger.info(
                f"📝 [Composio] Mapped source name '{source_short_name}' "
                f"to Composio slug '{composio_slug}'"
            )

        self.logger.info(f"📋 [Composio] Required auth fields: {source_auth_config_fields}")
        if optional_fields:
            self.logger.info(f"📋 [Composio] Optional auth fields: {optional_fields}")
        self.logger.info(
            f"🔑 [Composio] Using auth_config_id='{self.auth_config_id}', "
            f"account_id='{self.account_id}'"
        )

        async with httpx.AsyncClient() as client:
            # Get accounts matching the source
            source_connected_accounts = await self._get_source_connected_accounts(
                client, composio_slug, source_short_name
            )

            # Find the matching connection (also caches blob for get_config_for_source)
            source_creds_dict = self._find_matching_connection(
                source_connected_accounts, source_short_name
            )

            # Map and validate required fields
            found_credentials = self._map_and_validate_fields(
                source_creds_dict,
                source_auth_config_fields,
                source_short_name,
                optional_fields=optional_fields,
            )

            safe_log_credentials(
                found_credentials,
                self.logger.info,
                f"\n🔑 [Composio] Retrieved credentials for '{source_short_name}':",
            )
            return found_credentials

    async def _get_source_connected_accounts(
        self, client: httpx.AsyncClient, composio_slug: str, source_short_name: str
    ) -> List[Dict[str, Any]]:
        """Get connected accounts for a specific source from Composio.

        Args:
            client: HTTP client
            composio_slug: The Composio toolkit slug
            source_short_name: The original source short name

        Returns:
            List of connected accounts for the source

        Raises:
            HTTPException: If no accounts found for the source
        """
        self.logger.info("🌐 [Composio] Fetching connected accounts from Composio API...")

        all_connected_accounts = await self._get_all_connected_accounts(client)

        # Log all available toolkits/slugs for debugging
        all_toolkits = {
            acc.get("toolkit", {}).get("slug", "unknown") for acc in all_connected_accounts
        }
        self.logger.info(f"\n🔧 [Composio] Available toolkit slugs: {sorted(all_toolkits)}\n")

        source_connected_accounts = [
            connected_account
            for connected_account in all_connected_accounts
            if connected_account.get("toolkit", {}).get("slug") == composio_slug
        ]

        self.logger.info(
            f"\n🎯 [Composio] Found {len(source_connected_accounts)} accounts matching "
            f"slug '{composio_slug}'\n"
        )

        if not source_connected_accounts:
            self.logger.error(
                f"\n❌ [Composio] No connected accounts found for slug '{composio_slug}'. "
                f"Available slugs: {sorted(all_toolkits)}\n"
            )
            raise HTTPException(
                status_code=404,
                detail=f"No connected accounts found for source "
                f"'{source_short_name}' (Composio slug: '{composio_slug}') in Composio.",
            )

        # Log details of each matching account
        for i, account in enumerate(source_connected_accounts):
            acc_id = account.get("id")
            int_id = account.get("auth_config", {}).get("id")
            self.logger.info(
                f"\n  📌 Account {i + 1}: account_id='{acc_id}', auth_config_id='{int_id}'\n"
            )

        return source_connected_accounts

    def _find_matching_connection(
        self, source_connected_accounts: List[Dict[str, Any]], source_short_name: str
    ) -> Dict[str, Any]:
        """Find the matching connection in the list of connected accounts.

        Args:
            source_connected_accounts: List of connected accounts
            source_short_name: The source short name

        Returns:
            The credential dictionary for the matching connection

        Raises:
            HTTPException: If no matching connection found
        """
        source_creds_dict = None

        for connected_account in source_connected_accounts:
            account_id = connected_account.get("id")
            auth_config_id = connected_account.get("auth_config", {}).get("id")

            self.logger.debug(
                f"🔍 [Composio] Checking account: auth_config_id='{auth_config_id}' "
                f"(looking for '{self.auth_config_id}'), account_id='{account_id}' "
                f"(looking for '{self.account_id}')"
            )

            if auth_config_id == self.auth_config_id and account_id == self.account_id:
                self.logger.info(
                    f"\n✅ [Composio] Found matching connection! "
                    f"auth_config_id='{auth_config_id}', account_id='{account_id}'\n"
                )
                source_creds_dict = connected_account.get("state", {}).get("val")

                # Cache the full credential blob for get_config_for_source
                self._last_credential_blob = source_creds_dict

                # Log available credential fields
                if source_creds_dict:
                    available_fields = list(source_creds_dict.keys())
                    self.logger.info(
                        f"\n🔓 [Composio] Available credential fields: {available_fields}\n"
                    )
                    # Log credential fields safely without exposing values
                    sanitized_preview = sanitize_credentials_dict(
                        source_creds_dict, show_lengths=False
                    )
                    self.logger.debug(
                        f"\n🔓 [Composio] Credential fields preview: {sanitized_preview}\n"
                    )
                break

        if not source_creds_dict:
            self.logger.error(
                f"\n❌ [Composio] No matching connection found with "
                f"auth_config_id='{self.auth_config_id}' and account_id='{self.account_id}'\n"
            )
            raise HTTPException(
                status_code=404,
                detail=f"No matching connection in Composio with auth_config_id="
                f"'{self.auth_config_id}' and account_id='{self.account_id}' "
                f"for source '{source_short_name}'.",
            )

        return source_creds_dict

    def _map_and_validate_fields(
        self,
        source_creds_dict: Dict[str, Any],
        source_auth_config_fields: List[str],
        source_short_name: str,
        optional_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Map Airweave field names to Composio fields and validate required fields exist.

        Args:
            source_creds_dict: The credentials dictionary from Composio
            source_auth_config_fields: Auth fields to fetch
            source_short_name: The source short name
            optional_fields: Fields that can be skipped if not found in Composio

        Returns:
            Dictionary with mapped credentials

        Raises:
            HTTPException: If required (non-optional) fields are missing
        """
        missing_required_fields = []
        found_credentials = {}
        _optional_fields = optional_fields or set()

        self.logger.info("🔍 [Composio] Checking for auth fields...")

        for airweave_field in source_auth_config_fields:
            # Map the field name if needed
            composio_field = self._map_field_name(airweave_field)

            # For api_key field, try multiple possible field names in Composio
            # Some sources use generic_api_key (API key auth), others use access_token (OAuth)
            possible_fields = [composio_field]
            if airweave_field == "api_key":
                possible_fields.extend(["generic_api_key", "access_token"])
                # Remove duplicates while preserving order
                seen = set()
                possible_fields = [x for x in possible_fields if not (x in seen or seen.add(x))]

            found = False
            for field_to_check in possible_fields:
                if field_to_check in source_creds_dict:
                    # Store with the original Airweave field name
                    found_credentials[airweave_field] = source_creds_dict[field_to_check]
                    if airweave_field != field_to_check:
                        self.logger.info(
                            f"\n  🔄 Mapped field '{airweave_field}' to Composio field "
                            f"'{field_to_check}'\n"
                        )
                    self.logger.info(
                        f"\n  ✅ Found field: '{airweave_field}' (as '{field_to_check}' "
                        f"in Composio)\n"
                    )
                    found = True
                    break

            if not found:
                if airweave_field in _optional_fields:
                    self.logger.info(
                        f"\n  ⏭️ Skipping optional field: '{airweave_field}' "
                        f"(not available in Composio)\n"
                    )
                else:
                    missing_required_fields.append(airweave_field)
                    self.logger.warning(
                        f"\n  ❌ Missing required field: '{airweave_field}' (looked for "
                        f"{possible_fields} in Composio)\n"
                    )

        if missing_required_fields:
            available_fields = list(source_creds_dict.keys())
            self.logger.error(
                f"\n❌ [Composio] Missing required fields! "
                f"Required: {[f for f in source_auth_config_fields if f not in _optional_fields]}, "
                f"Missing: {missing_required_fields}, "
                f"Available in Composio: {available_fields}\n"
            )
            raise HTTPException(
                status_code=422,
                detail=f"Missing required auth fields for source '{source_short_name}': "
                f"{missing_required_fields}. "
                f"Available fields in Composio credentials: {available_fields}",
            )

        self.logger.info(
            f"\n✅ [Composio] Successfully retrieved {len(found_credentials)} "
            f"credential fields for source '{source_short_name}'\n"
        )

        return found_credentials

    async def get_config_for_source(
        self,
        source_short_name: str,
        source_config_field_mappings: Dict[str, str],
    ) -> Dict[str, Any]:
        """Extract config fields from the cached Composio credential blob.

        Called after get_creds_for_source which caches the full credential blob.

        Args:
            source_short_name: The short name of the source
            source_config_field_mappings: Mapping of config_field_name -> provider_field_name

        Returns:
            Dict of config field values found in the credential blob
        """
        blob = getattr(self, "_last_credential_blob", None) or {}
        result = {}
        for config_field, provider_field in source_config_field_mappings.items():
            if provider_field in blob:
                result[config_field] = blob[provider_field]
                self.logger.info(
                    f"🔧 [Composio] Extracted config field '{config_field}' "
                    f"from provider field '{provider_field}'"
                )
        return result

    async def validate(self) -> bool:
        """Validate that the Composio connection works by testing API access.

        Returns:
            True if the connection is valid

        Raises:
            HTTPException: If validation fails with detailed error message
        """
        try:
            self.logger.info("🔍 [Composio] Validating API key...")

            async with httpx.AsyncClient() as client:
                headers = {"x-api-key": self.api_key}

                # Test API access with the v3 connected accounts endpoint
                url = "https://backend.composio.dev/api/v3/connected_accounts"
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                self.logger.info("✅ [Composio] API key validated successfully")
                return True

        except httpx.HTTPStatusError as e:
            error_msg = f"Composio API key validation failed: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg += " - Invalid API key"
            elif e.response.status_code == 403:
                error_msg += " - Access denied"
            else:
                try:
                    error_detail = e.response.json().get("message", e.response.text)
                    error_msg += f" - {error_detail}"
                except Exception:
                    error_msg += f" - {e.response.text}"

            self.logger.error(f"❌ [Composio] {error_msg}")
            raise HTTPException(status_code=422, detail=error_msg)

        except Exception as e:
            error_msg = f"Composio API key validation failed: {str(e)}"
            self.logger.error(f"❌ [Composio] {error_msg}")
            raise HTTPException(status_code=422, detail=error_msg)
