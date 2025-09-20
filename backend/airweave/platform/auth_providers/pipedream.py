"""Pipedream Auth Provider - provides authentication services for other integrations."""

import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from airweave.core.credential_sanitizer import safe_log_credentials
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.decorators import auth_provider


@auth_provider(
    name="Pipedream",
    short_name="pipedream",
    auth_config_class="PipedreamAuthConfig",
    config_class="PipedreamConfig",
)
class PipedreamAuthProvider(BaseAuthProvider):
    """Pipedream authentication provider.

    IMPORTANT: This provider only works with custom OAuth clients created in Pipedream.
    Pipedream's default OAuth clients do not expose credentials via API for security reasons.

    Pipedream uses OAuth2 client credentials flow with access tokens that expire after 3600 seconds.
    """

    # Token expiry buffer (refresh 5 minutes before expiry)
    TOKEN_EXPIRY_BUFFER = 300  # 5 minutes in seconds

    # Pipedream OAuth token endpoint
    TOKEN_ENDPOINT = "https://api.pipedream.com/v1/oauth/token"

    BLOCKED_SOURCES = [
        "confluence",
        "jira",
        "bitbucket",
        "github",
        "ctti",
    ]

    # Mapping of Airweave field names to Pipedream field names
    # Key: Airweave field name, Value: Pipedream field name
    FIELD_NAME_MAPPING = {
        "api_key": "api_key",
        "access_token": "oauth_access_token",
        "refresh_token": "oauth_refresh_token",
        "client_id": "oauth_client_id",
        "client_secret": "oauth_client_secret",
        # Add more mappings as discovered
    }

    # Mapping of Airweave source short names to Pipedream app names
    # Key: Airweave short name, Value: Pipedream app name_slug
    SLUG_NAME_MAPPING = {
        "google_drive": "google_drive",
        "google_calendar": "google_calendar",
        "notion": "notion",
        "slack": "slack",
        "github": "github",
        "airtable": "airtable",
        "stripe": "stripe",
        "hubspot": "hubspot",
        "salesforce": "salesforce",
        "discord": "discord",
        "twitter": "twitter",
        "linkedin": "linkedin",
        "facebook": "facebook",
        "instagram": "instagram",
        "youtube": "youtube",
        "dropbox": "dropbox",
        "box": "box",
        "onedrive": "onedrive",
        "outlook_mail": "outlook",
        "outlook_calendar": "outlook",
        # Add more mappings as needed
    }

    @classmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "PipedreamAuthProvider":
        """Create a new Pipedream auth provider instance.

        Args:
            credentials: Auth credentials containing client_id and client_secret
            config: Configuration parameters including project_id, account_id, environment

        Returns:
            A Pipedream auth provider instance
        """
        if credentials is None:
            raise ValueError("credentials parameter is required")
        if config is None:
            raise ValueError("config parameter is required")

        instance = cls()
        instance.client_id = credentials["client_id"]
        instance.client_secret = credentials["client_secret"]
        instance.project_id = config["project_id"]
        instance.account_id = config["account_id"]
        instance.environment = config.get("environment", "production")
        instance.external_user_id = config.get("external_user_id")

        # Initialize token management
        instance._access_token = None
        instance._token_expires_at = 0

        return instance

    def _get_pipedream_app_slug(self, airweave_short_name: str) -> str:
        """Get the Pipedream app name_slug for an Airweave source short name.

        Args:
            airweave_short_name: The Airweave source short name

        Returns:
            The corresponding Pipedream app name_slug
        """
        return self.SLUG_NAME_MAPPING.get(airweave_short_name, airweave_short_name)

    def _map_field_name(self, airweave_field: str) -> str:
        """Map an Airweave field name to the corresponding Pipedream field name.

        Args:
            airweave_field: The Airweave field name

        Returns:
            The corresponding Pipedream field name
        """
        return self.FIELD_NAME_MAPPING.get(airweave_field, airweave_field)

    async def _ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if necessary.

        Returns:
            A valid access token

        Raises:
            HTTPException: If token refresh fails
        """
        current_time = time.time()

        # Check if token needs refresh
        if self._access_token and self._token_expires_at > (
            current_time + self.TOKEN_EXPIRY_BUFFER
        ):
            return self._access_token

        # Need to refresh token
        self.logger.info("🔄 [Pipedream] Refreshing access token...")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_ENDPOINT,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                response.raise_for_status()

                token_data = response.json()
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
                self._token_expires_at = current_time + expires_in

                self.logger.info(
                    f"✅ [Pipedream] Successfully refreshed token (expires in {expires_in}s)"
                )

                return self._access_token

            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"❌ [Pipedream] Failed to refresh token: {e.response.status_code} - "
                    f"{e.response.text}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to refresh Pipedream access token: {e.response.text}",
                ) from e

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Pipedream access token.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        # Ensure we have a valid token
        access_token = await self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-pd-environment": self.environment,
        }

        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"❌ [Pipedream] API request failed: {e.response.status_code} - {e.response.text}"
            )
            raise

    async def get_creds_for_source(
        self, source_short_name: str, source_auth_config_fields: List[str]
    ) -> Dict[str, Any]:
        """Get credentials for a source from Pipedream.

        Args:
            source_short_name: The short name of the source to get credentials for
            source_auth_config_fields: The fields required for the source auth config

        Returns:
            Credentials dictionary for the source

        Raises:
            HTTPException: If no credentials found for the source
        """
        # Map Airweave source name to Pipedream app slug if needed
        pipedream_app_slug = self._get_pipedream_app_slug(source_short_name)

        self.logger.info(
            f"🔍 [Pipedream] Starting credential retrieval for source '{source_short_name}'"
        )
        if pipedream_app_slug != source_short_name:
            self.logger.info(
                f"📝 [Pipedream] Mapped source name '{source_short_name}' "
                f"to Pipedream app slug '{pipedream_app_slug}'"
            )

        self.logger.info(f"📋 [Pipedream] Required auth fields: {source_auth_config_fields}")
        self.logger.info(
            f"🔑 [Pipedream] Using project_id='{self.project_id}', "
            f"account_id='{self.account_id}', environment='{self.environment}'"
        )

        async with httpx.AsyncClient() as client:
            # Get the specific account with credentials
            account_data = await self._get_account_with_credentials(
                client, pipedream_app_slug, source_short_name
            )

            # Extract and map credentials
            found_credentials = self._extract_and_map_credentials(
                account_data, source_auth_config_fields, source_short_name
            )

            safe_log_credentials(
                found_credentials,
                self.logger.info,
                f"\n🔑 [Pipedream] Retrieved credentials for '{source_short_name}':",
            )
            return found_credentials

    async def _get_account_with_credentials(
        self, client: httpx.AsyncClient, pipedream_app_slug: str, source_short_name: str
    ) -> Dict[str, Any]:
        """Get specific account with credentials from Pipedream.

        Args:
            client: HTTP client
            pipedream_app_slug: The Pipedream app name_slug
            source_short_name: The original source short name

        Returns:
            Account data with credentials

        Raises:
            HTTPException: If account not found or credentials not available
        """
        # Build the API URL for the specific account
        url = f"https://api.pipedream.com/v1/connect/{self.project_id}/accounts/{self.account_id}"

        self.logger.info(f"🌐 [Pipedream] Fetching account from: {url}")

        try:
            # Include credentials in the response
            params = {"include_credentials": "true"}
            account_data = await self._get_with_auth(client, url, params)

            # Verify it's the right app
            if account_data.get("app", {}).get("name_slug") != pipedream_app_slug:
                self.logger.error(
                    f"❌ [Pipedream] Account app mismatch. Expected '{pipedream_app_slug}', "
                    f"got '{account_data.get('app', {}).get('name_slug')}'"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Account {self.account_id} is not for app '{pipedream_app_slug}'",
                )

            # Check if credentials are included
            if "credentials" not in account_data:
                self.logger.error(
                    "❌ [Pipedream] No credentials in response. This usually means the account "
                    "was created with Pipedream's default OAuth client, not a custom one."
                )
                raise HTTPException(
                    status_code=422,
                    detail="Credentials not available. Pipedream only exposes credentials for "
                    "accounts created with custom OAuth clients, not default Pipedream OAuth.",
                )

            self.logger.info(
                f"✅ [Pipedream] Found account '{account_data.get('name')}' "
                f"with credentials for app '{pipedream_app_slug}'"
            )

            return account_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"Pipedream account not found: {self.account_id}"
                ) from e
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch Pipedream account: {e.response.text}",
            ) from e

    def _extract_and_map_credentials(
        self,
        account_data: Dict[str, Any],
        source_auth_config_fields: List[str],
        source_short_name: str,
    ) -> Dict[str, Any]:
        """Extract and map credentials from Pipedream account data.

        Args:
            account_data: The account data from Pipedream
            source_auth_config_fields: Required auth fields
            source_short_name: The source short name

        Returns:
            Dictionary with mapped credentials

        Raises:
            HTTPException: If required fields are missing
        """
        credentials = account_data.get("credentials", {})
        missing_fields = []
        found_credentials = {}

        self.logger.info("🔍 [Pipedream] Checking for required auth fields...")
        self.logger.info(f"📦 [Pipedream] Available credential fields: {list(credentials.keys())}")

        for airweave_field in source_auth_config_fields:
            # Map the field name if needed
            pipedream_field = self._map_field_name(airweave_field)

            if airweave_field != pipedream_field:
                self.logger.info(
                    f"\n  🔄 Mapped field '{airweave_field}' to Pipedream field "
                    f"'{pipedream_field}'\n"
                )

            if pipedream_field in credentials:
                # Store with the original Airweave field name
                found_credentials[airweave_field] = credentials[pipedream_field]
                self.logger.info(
                    f"\n  ✅ Found field: '{airweave_field}' (as '{pipedream_field}' "
                    f"in Pipedream)\n"
                )
            else:
                missing_fields.append(airweave_field)
                self.logger.warning(
                    f"\n  ❌ Missing field: '{airweave_field}' (looked for "
                    f"'{pipedream_field}' in Pipedream)\n"
                )

        if missing_fields:
            available_fields = list(credentials.keys())
            self.logger.error(
                f"\n❌ [Pipedream] Missing required fields! "
                f"Required: {source_auth_config_fields}, "
                f"Missing: {missing_fields}, "
                f"Available in Pipedream: {available_fields}\n"
            )
            raise HTTPException(
                status_code=422,
                detail=f"Missing required auth fields for source '{source_short_name}': "
                f"{missing_fields}. "
                f"Required fields: {source_auth_config_fields}. "
                f"Available fields in Pipedream credentials: {available_fields}",
            )

        self.logger.info(
            f"\n✅ [Pipedream] Successfully retrieved all {len(found_credentials)} required "
            f"credential fields for source '{source_short_name}'\n"
        )

        return found_credentials
