"""Custom Auth Provider - fetches tokens from a customer-hosted HTTP endpoint."""

from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import httpx

from airweave.domains.auth_provider._base import BaseAuthProvider
from airweave.domains.auth_provider.exceptions import (
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderTemporaryError,
)
from airweave.platform.configs.auth import CustomAuthConfig
from airweave.platform.configs.config import CustomConfig
from airweave.platform.decorators import auth_provider
from airweave.platform.utils.ssrf import SSRFViolation, validate_url


@auth_provider(
    name="Custom",
    short_name="custom",
    auth_config_class=CustomAuthConfig,
    config_class=CustomConfig,
    feature_flag="custom_auth_provider",
)
class CustomAuthProvider(BaseAuthProvider):
    """Custom authentication provider.

    Calls GET {base_url}/{source_connection_id} on a customer-hosted endpoint
    to fetch fresh credentials. The customer is responsible for returning
    the freshest credentials as JSON.
    """

    BLOCKED_SOURCES: list[str] = []

    # Map Airweave-internal field names to the simple names customers return.
    # Customers always return {"access_token": "..."} or {"api_key": "..."}.
    FIELD_NAME_MAPPING: Dict[str, str] = {
        "personal_access_token": "access_token",  # GitHub
        "api_token": "access_token",  # Document360, Pipedrive
    }

    @classmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "CustomAuthProvider":
        """Create a new Custom auth provider instance."""
        instance = cls()
        instance.endpoint_url = credentials["endpoint_url"].rstrip("/")
        instance.api_key = credentials["api_key"]
        return instance

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with API key authentication."""
        return {
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

    def _check_ssrf(self, url: str) -> None:
        """Validate URL against SSRF blocklist before making a request."""
        try:
            validate_url(url)
        except SSRFViolation as exc:
            self.logger.warning(f"[Custom] SSRF blocked: {exc}")
            raise AuthProviderConfigError(
                f"Custom endpoint URL blocked by SSRF policy: {exc}",
                provider_name="custom",
            ) from exc

    async def get_creds_for_source(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
        source_connection_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get credentials for a source by calling GET {base_url}/{source_connection_id}."""
        if not source_connection_id:
            raise AuthProviderConfigError(
                "Custom auth provider requires a source_connection_id",
                provider_name="custom",
            )
        _optional_fields = optional_fields or set()
        headers = self._build_headers()
        url = f"{self.endpoint_url}/{source_connection_id}"

        self._check_ssrf(url)
        self.logger.info(f"[Custom] Fetching credentials for source '{source_short_name}'")

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                self.logger.error(
                    f"[Custom] HTTP {status} from endpoint for source '{source_short_name}'"
                )
                if status in (401, 403):
                    raise AuthProviderAuthError(
                        f"Custom endpoint returned {status} for source '{source_short_name}'",
                        provider_name="custom",
                    ) from e
                if status == 429:
                    retry_after = float(e.response.headers.get("retry-after", 30))
                    raise AuthProviderRateLimitError(
                        f"Custom endpoint rate-limited for source '{source_short_name}'",
                        provider_name="custom",
                        retry_after=retry_after,
                    ) from e
                if status == 404:
                    raise AuthProviderMissingFieldsError(
                        f"Custom endpoint has no credentials configured for "
                        f"source '{source_short_name}' (404)",
                        provider_name="custom",
                        missing_fields=[],
                        available_fields=[],
                    ) from e
                if status >= 500:
                    raise AuthProviderTemporaryError(
                        f"Custom endpoint returned {status} for source '{source_short_name}'",
                        provider_name="custom",
                        status_code=status,
                    ) from e
                raise AuthProviderConfigError(
                    f"Custom endpoint returned unexpected {status} for "
                    f"source '{source_short_name}'",
                    provider_name="custom",
                ) from e
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self.logger.error(f"[Custom] Network error reaching endpoint: {e}")
                raise AuthProviderTemporaryError(
                    f"Custom endpoint unreachable: {e}",
                    provider_name="custom",
                ) from e

        missing_fields = []
        found_credentials: Dict[str, Any] = {}

        for field in source_auth_config_fields:
            # Check the response using the mapped name (e.g. access_token for
            # personal_access_token), then store under the Airweave-internal name.
            mapped = self.FIELD_NAME_MAPPING.get(field, field)
            if mapped in data:
                found_credentials[field] = data[mapped]
            elif field in data:
                found_credentials[field] = data[field]
            elif field not in _optional_fields:
                missing_fields.append(mapped)

        if missing_fields:
            available = list(data.keys())
            self.logger.error(
                f"[Custom] Missing required fields for source '{source_short_name}': "
                f"{missing_fields}. Available: {available}"
            )
            raise AuthProviderMissingFieldsError(
                f"Custom endpoint response missing required fields for "
                f"source '{source_short_name}': {missing_fields}",
                provider_name="custom",
                missing_fields=missing_fields,
                available_fields=available,
            )

        self.logger.info(
            f"[Custom] Successfully retrieved {len(found_credentials)} credential fields "
            f"for source '{source_short_name}'"
        )
        return found_credentials

    async def validate(self) -> bool:
        """Validate the custom endpoint by calling GET {base_url}."""
        headers = self._build_headers()
        url = self.endpoint_url

        self._check_ssrf(url)
        self.logger.info("[Custom] Validating endpoint")

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                self.logger.info("[Custom] Endpoint validated successfully")
                return True

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in (401, 403):
                raise AuthProviderAuthError(
                    f"Custom endpoint validation failed: {status}",
                    provider_name="custom",
                ) from e
            if status >= 500:
                raise AuthProviderTemporaryError(
                    f"Custom endpoint validation failed: {status}",
                    provider_name="custom",
                    status_code=status,
                ) from e
            raise AuthProviderConfigError(
                f"Custom endpoint validation failed: HTTP {status}",
                provider_name="custom",
            ) from e
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise AuthProviderTemporaryError(
                f"Custom endpoint unreachable during validation: {e}",
                provider_name="custom",
            ) from e
