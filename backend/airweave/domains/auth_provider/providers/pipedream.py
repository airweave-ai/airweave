"""Pipedream Auth Provider - provides authentication services for other integrations."""

import time
from typing import Any, Dict, List, Optional, Set

import httpx

from airweave.core.credential_sanitizer import safe_log_credentials
from airweave.domains.auth_provider._base import BaseAuthProvider
from airweave.domains.auth_provider.auth_result import AuthResult
from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderTemporaryError,
)
from airweave.platform.configs.auth import PipedreamAuthConfig
from airweave.platform.configs.config import PipedreamConfig
from airweave.platform.decorators import auth_provider


class PipedreamDefaultOAuthException(Exception):
    """Raised when trying to access credentials for a Pipedream default OAuth client.

    This happens when the connected account uses Pipedream's built-in OAuth client
    rather than a custom OAuth client. In this case, credentials cannot be retrieved
    directly. Users must connect using a custom OAuth client instead.
    """

    def __init__(self, source_short_name: str, message: str = None):
        """Initialize the exception."""
        self.source_short_name = source_short_name
        if message is None:
            message = (
                f"Cannot retrieve credentials for {source_short_name}. "
                "This account uses Pipedream's default OAuth client. "
                "Please connect using a custom OAuth client."
            )
        super().__init__(message)


@auth_provider(
    name="Pipedream",
    short_name="pipedream",
    auth_config_class=PipedreamAuthConfig,
    config_class=PipedreamConfig,
)
class PipedreamAuthProvider(BaseAuthProvider):
    """Pipedream authentication provider.

    IMPORTANT: This provider only works with custom OAuth clients created in Pipedream.
    Pipedream's default OAuth clients do not expose credentials via API for security reasons.

    Pipedream uses OAuth2 client credentials flow with access tokens that expire after 3600 seconds.
    """

    SETTINGS_URL = "https://pipedream.com/settings/api"

    # Token expiry buffer (refresh 10 minutes before expiry)
    # This ensures tokens are refreshed well before expiry during long-running syncs
    TOKEN_EXPIRY_BUFFER = 600  # 10 minutes in seconds

    # Pipedream OAuth token endpoint
    TOKEN_ENDPOINT = "https://api.pipedream.com/v1/oauth/token"

    # Sources that Pipedream does not support
    BLOCKED_SOURCES = [
        "ctti",
        "github",
        # Atlassian constructs the URL using a cloud ID which Pipedream does not provide
        "jira",
        "confluence",
        # Workspace needs to be moved to the regular config, which will conflict with Composio
        "bitbucket",
        "onenote",
        "word",
        "servicenow",
    ]

    # Mapping of Airweave field names to Pipedream field names
    # Key: Airweave field name, Value: Pipedream field name
    FIELD_NAME_MAPPING = {
        "api_key": "api_key",
        "api_token": "api_key",  # Document360 and other sources use api_token
        "access_token": "oauth_access_token",
        "refresh_token": "oauth_refresh_token",
        "client_id": "oauth_client_id",
        "client_secret": "oauth_client_secret",
        "personal_access_token": "oauth_access_token",  # GitHub PAT mapping
        # Add more mappings as discovered
    }

    # Mapping of Airweave source short names to Pipedream app names
    # Key: Airweave short name, Value: Pipedream app name_slug
    # Only include mappings where names differ between Airweave and Pipedream
    SLUG_NAME_MAPPING = {
        "apollo": "apollo_io",  # Pipedream app name_slug is apollo_io
        "outlook_mail": "outlook",
        "outlook_calendar": "outlook",
        "slack": "slack_v2",  # Pipedream uses slack_v2 for their newer Slack app
        "powerpoint": "microsoft_onedrive",
        "calcom": "cal_com",
        # Add more mappings as needed when names differ
    }

    # Per-source override for field names (Airweave field -> Pipedream field).
    # Use when a source's auth config uses one name but Pipedream returns another.
    SOURCE_FIELD_MAPPING = {
        "coda": {"api_key": "api_token"},  # Pipedream Coda app uses api_token
        "slab": {"api_key": "api_token"},  # Pipedream Slab app uses api_token
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
            config = {}

        instance = cls()
        instance.client_id = credentials["client_id"]
        instance.client_secret = credentials["client_secret"]
        instance.project_id = config.get("project_id")
        instance.account_id = config.get("account_id")
        instance.external_user_id = config.get("external_user_id")
        instance.environment = config.get("environment", "production")

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

    def _map_field_name(self, airweave_field: str, source_short_name: Optional[str] = None) -> str:
        """Map an Airweave field name to the corresponding Pipedream field name.

        Args:
            airweave_field: The Airweave field name
            source_short_name: Optional source short name for per-source override

        Returns:
            The corresponding Pipedream field name
        """
        if source_short_name:
            source_map = self.SOURCE_FIELD_MAPPING.get(source_short_name, {})
            if airweave_field in source_map:
                return source_map[airweave_field]
        return self.FIELD_NAME_MAPPING.get(airweave_field, airweave_field)

    async def _ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if necessary.

        Returns:
            A valid access token

        Raises:
            AuthProviderAuthError: If client credentials are rejected.
            AuthProviderRateLimitError: If token endpoint is rate-limited.
            AuthProviderTemporaryError: If token endpoint returns a server error.
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
                status = e.response.status_code
                self.logger.error(
                    f"❌ [Pipedream] Failed to refresh token: {status} {e.response.reason_phrase}"
                )
                if status == 401:
                    raise AuthProviderAuthError(
                        f"Pipedream rejected client credentials ({status})",
                        provider_name="pipedream",
                    ) from e
                if status == 429:
                    retry_after = float(e.response.headers.get("retry-after", 30))
                    raise AuthProviderRateLimitError(
                        "Pipedream token endpoint rate-limited",
                        provider_name="pipedream",
                        retry_after=retry_after,
                    ) from e
                raise AuthProviderTemporaryError(
                    f"Pipedream token endpoint returned {status}",
                    provider_name="pipedream",
                    status_code=status,
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
                f"❌ [Pipedream] API request failed: "
                f"{e.response.status_code} {e.response.reason_phrase}"
            )
            raise

    async def get_creds_for_source(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get credentials for a source from Pipedream.

        Args:
            source_short_name: The short name of the source to get credentials for
            source_auth_config_fields: The fields required for the source auth config
            optional_fields: Fields that can be skipped if not available in Pipedream

        Returns:
            Credentials dictionary for the source

        Raises:
            AuthProviderAccountNotFoundError: If the account is not found.
            AuthProviderMissingFieldsError: If required credential fields are absent.
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
        if optional_fields:
            self.logger.info(f"📋 [Pipedream] Optional auth fields: {optional_fields}")
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
                account_data,
                source_auth_config_fields,
                source_short_name,
                optional_fields=optional_fields,
            )

            safe_log_credentials(
                found_credentials,
                self.logger.info,
                f"[Pipedream] Retrieved credentials for '{source_short_name}':",
            )
            return found_credentials

    async def validate(self) -> bool:
        """Validate that the Pipedream connection works by testing client credentials.

        Returns:
            True if the connection is valid.

        Raises:
            AuthProviderAuthError: Invalid client credentials (401).
            AuthProviderConfigError: Bad request or unexpected response.
            AuthProviderTemporaryError: Transient failure from Pipedream.
        """
        try:
            self.logger.info("🔍 [Pipedream] Validating client credentials...")

            async with httpx.AsyncClient() as client:
                token_data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }

                response = await client.post(self.TOKEN_ENDPOINT, data=token_data)
                response.raise_for_status()

                token_response = response.json()
                if "access_token" not in token_response:
                    raise AuthProviderConfigError(
                        "Pipedream API returned token response without access_token",
                        provider_name="pipedream",
                    )

                self.logger.info("✅ [Pipedream] Client credentials validated successfully")
                return True

        except AuthProviderConfigError:
            raise
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                error_msg = (
                    "Pipedream client credentials validation failed: Invalid client credentials"
                )
                self.logger.error(f"❌ [Pipedream] {error_msg}")
                raise AuthProviderAuthError(error_msg, provider_name="pipedream") from e

            try:
                body = e.response.json()
                detail = body.get("error_description", body.get("error", f"HTTP {status}"))
            except Exception:
                detail = e.response.text or f"HTTP {status}"

            error_msg = f"Pipedream client credentials validation failed: {status} - {detail}"
            self.logger.error(f"❌ [Pipedream] {error_msg}")

            if status >= 500:
                raise AuthProviderTemporaryError(
                    error_msg, provider_name="pipedream", status_code=status
                ) from e
            raise AuthProviderConfigError(error_msg, provider_name="pipedream") from e

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            error_msg = f"Pipedream unreachable during validation: {e}"
            self.logger.error(f"❌ [Pipedream] {error_msg}")
            raise AuthProviderTemporaryError(error_msg, provider_name="pipedream") from e

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
            AuthProviderAccountNotFoundError: Account does not exist.
            AuthProviderConfigError: Account is for a different app.
            PipedreamDefaultOAuthException: Default OAuth — credentials not available.
            AuthProviderTemporaryError: Transient HTTP failure.
        """
        url = f"https://api.pipedream.com/v1/connect/{self.project_id}/accounts/{self.account_id}"

        self.logger.info(f"🌐 [Pipedream] Fetching account from: {url}")

        try:
            params = {"include_credentials": "true"}
            account_data = await self._get_with_auth(client, url, params)

            if account_data.get("app", {}).get("name_slug") != pipedream_app_slug:
                actual = account_data.get("app", {}).get("name_slug")
                self.logger.error(
                    f"❌ [Pipedream] Account app mismatch. "
                    f"Expected '{pipedream_app_slug}', got '{actual}'"
                )
                raise AuthProviderConfigError(
                    f"Account {self.account_id} is for app '{actual}', "
                    f"expected '{pipedream_app_slug}'",
                    provider_name="pipedream",
                )

            if "credentials" not in account_data:
                self.logger.error(
                    "❌ [Pipedream] No credentials in response. This usually means "
                    "the account was created with Pipedream's default OAuth client."
                )
                raise PipedreamDefaultOAuthException(source_short_name)

            self.logger.info(
                f"✅ [Pipedream] Found account '{account_data.get('name')}' "
                f"with credentials for app '{pipedream_app_slug}'"
            )

            return account_data

        except (AuthProviderConfigError, PipedreamDefaultOAuthException):
            raise
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                raise AuthProviderAccountNotFoundError(
                    f"Pipedream account not found: {self.account_id}",
                    provider_name="pipedream",
                    account_id=self.account_id,
                ) from e
            if status == 429:
                retry_after = float(e.response.headers.get("retry-after", 30))
                raise AuthProviderRateLimitError(
                    "Pipedream API rate-limited while fetching account",
                    provider_name="pipedream",
                    retry_after=retry_after,
                ) from e
            if status >= 500:
                raise AuthProviderTemporaryError(
                    f"Pipedream API returned {status} while fetching account",
                    provider_name="pipedream",
                    status_code=status,
                ) from e
            try:
                body = e.response.json()
                error_code = body.get("error", "")
                msg = (
                    f"Pipedream API error {status}: {error_code}"
                    if error_code
                    else f"Pipedream API error {status}"
                )
            except Exception:
                msg = f"Pipedream API error {status}"
            raise AuthProviderTemporaryError(
                msg,
                provider_name="pipedream",
                status_code=status,
            ) from e

    def _extract_and_map_credentials(
        self,
        account_data: Dict[str, Any],
        source_auth_config_fields: List[str],
        source_short_name: str,
        optional_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Extract and map credentials from Pipedream account data.

        Args:
            account_data: The account data from Pipedream
            source_auth_config_fields: Auth fields to fetch
            source_short_name: The source short name
            optional_fields: Fields that can be skipped if not found in Pipedream

        Returns:
            Dictionary with mapped credentials

        Raises:
            AuthProviderMissingFieldsError: If required fields are absent.
        """
        credentials = account_data.get("credentials", {})
        missing_required_fields = []
        found_credentials = {}
        _optional_fields = optional_fields or set()

        self.logger.info("🔍 [Pipedream] Checking for auth fields...")
        self.logger.info(f"📦 [Pipedream] Available credential fields: {list(credentials.keys())}")

        for airweave_field in source_auth_config_fields:
            pipedream_field = self._map_field_name(
                airweave_field, source_short_name=source_short_name
            )

            if airweave_field != pipedream_field:
                self.logger.info(
                    f"[Pipedream] Mapped field '{airweave_field}' "
                    f"to Pipedream field '{pipedream_field}'"
                )

            if pipedream_field in credentials:
                found_credentials[airweave_field] = credentials[pipedream_field]
                self.logger.info(
                    f"[Pipedream] Found field: '{airweave_field}' "
                    f"(as '{pipedream_field}' in Pipedream)"
                )
            else:
                if airweave_field in _optional_fields:
                    self.logger.info(
                        f"[Pipedream] Skipping optional field: '{airweave_field}' "
                        f"(not available in Pipedream)"
                    )
                else:
                    missing_required_fields.append(airweave_field)
                    self.logger.warning(
                        f"[Pipedream] Missing required field: '{airweave_field}' "
                        f"(looked for '{pipedream_field}' in Pipedream)"
                    )

        if missing_required_fields:
            available_fields = list(credentials.keys())
            self.logger.error(
                f"[Pipedream] Missing required fields! "
                f"Required: {[f for f in source_auth_config_fields if f not in _optional_fields]}, "
                f"Missing: {missing_required_fields}, "
                f"Available in Pipedream: {available_fields}"
            )
            raise AuthProviderMissingFieldsError(
                f"Missing required auth fields for source '{source_short_name}': "
                f"{missing_required_fields}",
                provider_name="pipedream",
                missing_fields=missing_required_fields,
                available_fields=available_fields,
            )

        self.logger.info(
            f"[Pipedream] Successfully retrieved {len(found_credentials)} "
            f"credential fields for source '{source_short_name}'"
        )

        return found_credentials

    async def get_auth_result(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
        source_config_field_mappings: Optional[Dict[str, str]] = None,
    ) -> AuthResult:
        """Get auth result for Pipedream.

        Only sources with custom OAuth clients are supported. Blocked sources
        and default OAuth clients raise errors.
        """
        if source_short_name in self.BLOCKED_SOURCES:
            raise AuthProviderConfigError(
                f"Source '{source_short_name}' is not supported via Pipedream.",
                provider_name="pipedream",
            )

        try:
            credentials = await self.get_creds_for_source(
                source_short_name, source_auth_config_fields, optional_fields
            )
            self.logger.info(
                f"Custom OAuth client detected for {source_short_name} - using direct mode"
            )
            result = AuthResult.direct(credentials)

            if source_config_field_mappings:
                source_config = await self.get_config_for_source(
                    source_short_name, source_config_field_mappings
                )
                result.source_config = source_config or None

            return result

        except PipedreamDefaultOAuthException:
            raise AuthProviderConfigError(
                f"Source '{source_short_name}' uses Pipedream's default OAuth client "
                f"which does not expose credentials. "
                f"Please connect using a custom OAuth client.",
                provider_name="pipedream",
            )
