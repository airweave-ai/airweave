"""Auth0 identity adapter.

Contains both the low-level Management API HTTP client and the
IdentityProvider adapter that domain code depends on.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.core.protocols.identity import (
    IdentityProvider,
    IdentityProviderConflictError,
    IdentityProviderError,
    IdentityProviderNotFoundError,
    IdentityProviderRateLimitError,
    IdentityProviderUnavailableError,
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class Auth0RateLimitError(Exception):
    """Custom exception for Auth0 rate limit errors."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        """Initialize Auth0RateLimitError."""
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Low-level HTTP client
# ---------------------------------------------------------------------------


class Auth0ManagementClient:
    """Client for Auth0 Management API operations."""

    DEFAULT_TIMEOUT = 20.0
    INVITATION_TIMEOUT = 10.0
    MAX_RETRIES = 5
    MIN_RETRY_WAIT = 1  # seconds
    MAX_RETRY_WAIT = 60  # seconds

    def __init__(self) -> None:
        """Initialize Auth0ManagementClient."""
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_M2M_CLIENT_ID
        self.client_secret = settings.AUTH0_M2M_CLIENT_SECRET
        self.audience = f"https://{self.domain}/api/v2/"
        self.base_url = f"https://{self.domain}/api/v2"

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, Auth0RateLimitError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        before_sleep=before_sleep_log(logger, logging.INFO),  # type: ignore[arg-type]
    )
    async def _get_management_token(self) -> str:
        """Get Auth0 Management API access token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.domain}/oauth/token",
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "audience": self.audience,
                        "grant_type": "client_credentials",
                    },
                    timeout=self.DEFAULT_TIMEOUT,
                )

                if response.status_code == 429:
                    retry_after = self._get_retry_after(response)
                    error_msg = "Auth0 token endpoint rate limit exceeded"
                    if retry_after:
                        logger.warning(f"{error_msg}. Retry after {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                    raise Auth0RateLimitError(error_msg, retry_after)

                response.raise_for_status()
                data = response.json()
                token = data["access_token"]
                logger.info("Successfully obtained Auth0 Management API token")
                return token  # type: ignore[no-any-return]
        except (httpx.HTTPStatusError, Auth0RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Failed to get Auth0 Management API token: {e}")
            raise

    def _get_retry_after(self, response: httpx.Response) -> Optional[int]:
        """Extract retry-after header value from response."""
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                logger.warning(f"Invalid retry-after header value: {retry_after}")
        return None

    @retry(
        retry=retry_if_exception_type(Auth0RateLimitError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_RETRY_WAIT, max=MAX_RETRY_WAIT),
        before_sleep=before_sleep_log(logger, logging.INFO),  # type: ignore[arg-type]
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        timeout: float = DEFAULT_TIMEOUT,
        return_empty_list_on_error: bool = False,
    ) -> Dict | List[Dict] | None:
        """Make an authenticated request to the Auth0 Management API.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            json_data: JSON payload for POST/PUT requests
            timeout: Request timeout in seconds
            return_empty_list_on_error: Return empty list instead of raising on error

        Returns:
            Response data or None for empty responses
        """
        try:
            token = await self._get_management_token()
            headers = {"Authorization": f"Bearer {token}"}
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    timeout=timeout,
                )

                if response.status_code == 429:
                    retry_after = self._get_retry_after(response)
                    error_msg = f"Auth0 API rate limit exceeded for {method} {endpoint}"
                    if retry_after:
                        logger.warning(f"{error_msg}. Retry after {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                    raise Auth0RateLimitError(error_msg, retry_after)

                response.raise_for_status()

                if not response.content:
                    return None

                return response.json()  # type: ignore[no-any-return]

        except Auth0RateLimitError:
            raise
        except Exception as e:
            if return_empty_list_on_error:
                logger.error(f"Auth0 API request failed for {method} {endpoint}: {e}")
                return []
            raise

    # -- Organization management --

    async def create_organization(self, name: str, display_name: str) -> Dict:
        """Create a new Auth0 organization."""
        try:
            org_name = name.lower().replace(" ", "-").replace("_", "-")
            org_data = await self._make_request(
                "POST", "/organizations", json_data={"name": org_name, "display_name": display_name}
            )
            logger.info(f"Successfully created Auth0 organization: {org_data['id']}")  # type: ignore[call-overload, index]
            return org_data  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Failed to create Auth0 organization: {e}")
            raise

    async def delete_organization(self, org_id: str) -> None:
        """Delete an Auth0 organization."""
        try:
            await self._make_request("DELETE", f"/organizations/{org_id}")
            logger.info(f"Successfully deleted Auth0 organization: {org_id}")
        except Exception as e:
            logger.error(f"Failed to delete Auth0 organization: {e}")
            raise

    # -- User-organization relationships --

    async def get_user_organizations(self, auth0_user_id: str) -> List[Dict]:
        """Get organizations a user belongs to."""
        return await self._make_request(  # type: ignore[return-value]
            "GET", f"/users/{auth0_user_id}/organizations", return_empty_list_on_error=True
        )

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """Add user to Auth0 organization."""
        try:
            await self._make_request(
                "POST", f"/organizations/{org_id}/members", json_data={"members": [user_id]}
            )
            logger.info(f"Successfully added user {user_id} to Auth0 organization {org_id}")
        except Exception as e:
            logger.error(f"Failed to add user to Auth0 organization: {e}")
            raise

    async def remove_user_from_organization(self, org_id: str, user_id: str) -> None:
        """Remove user from Auth0 organization."""
        try:
            await self._make_request(
                "DELETE", f"/organizations/{org_id}/members", json_data={"members": [user_id]}
            )
            logger.info(f"Successfully removed user {user_id} from Auth0 organization {org_id}")
        except Exception as e:
            logger.error(f"Failed to remove user from Auth0 organization: {e}")
            raise

    async def get_organization_members(self, org_id: str) -> List[Dict]:
        """Get all members of an organization."""
        return await self._make_request(  # type: ignore[return-value]
            "GET", f"/organizations/{org_id}/members", return_empty_list_on_error=True
        )

    # -- Roles & invitations --

    async def get_roles(self) -> List[Dict]:
        """Get all roles from Auth0."""
        try:
            return await self._make_request("GET", "/roles")  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Auth0 API error getting roles: {e}")
            raise

    async def invite_user_to_organization(
        self, org_id: str, email: str, role: str = "member", inviter_user: Optional[Any] = None
    ) -> Dict:
        """Send Auth0 organization invitation."""
        try:
            inviter_name = (
                f"{inviter_user.full_name} ({inviter_user.email})"
                if inviter_user
                else "Airweave Platform"
            )

            all_roles = await self.get_roles()
            role_id = next((r["id"] for r in all_roles if r["name"] == role), None)

            if not role_id:
                logger.error(f"Role '{role}' not found in Auth0. Cannot send invitation.")
                raise ValueError(f"Role '{role}' not found.")

            invitation_data = await self._make_request(
                "POST",
                f"/organizations/{org_id}/invitations",
                json_data={
                    "inviter": {"name": inviter_name},
                    "invitee": {"email": email},
                    "client_id": settings.AUTH0_CLIENT_ID,
                    "roles": [role_id],
                },
                timeout=self.INVITATION_TIMEOUT,
            )

            logger.info(f"Successfully sent Auth0 invitation to {email} for organization {org_id}")
            return invitation_data  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Failed to send Auth0 invitation: {e}")
            raise

    async def get_pending_invitations(self, org_id: str) -> List[Dict]:
        """Get pending invitations for organization."""
        return await self._make_request(  # type: ignore[return-value]
            "GET",
            f"/organizations/{org_id}/invitations",
            timeout=self.INVITATION_TIMEOUT,
            return_empty_list_on_error=True,
        )

    async def delete_invitation(self, org_id: str, invitation_id: str) -> None:
        """Delete a pending invitation."""
        try:
            await self._make_request(
                "DELETE",
                f"/organizations/{org_id}/invitations/{invitation_id}",
                timeout=self.INVITATION_TIMEOUT,
            )
            logger.info(
                f"Successfully deleted invitation {invitation_id} from organization {org_id}"
            )
        except Exception as e:
            logger.error(f"Failed to delete invitation from Auth0: {e}")
            raise

    async def get_organization_member_roles(self, org_id: str, user_id: str) -> List[Dict]:
        """Get roles for a specific member of an organization."""
        return await self._make_request("GET", f"/organizations/{org_id}/members/{user_id}/roles")  # type: ignore[return-value]

    # -- Connections --

    async def get_all_connections(self) -> List[Dict]:
        """Get all connections from Auth0."""
        try:
            return await self._make_request("GET", "/connections")  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Auth0 API error getting all connections: {e}")
            raise

    async def add_enabled_connection_to_organization(
        self, auth0_org_id: str, connection_id: str
    ) -> None:
        """Enable a connection for an organization in Auth0."""
        body = {"connection_id": connection_id, "assign_membership_on_login": False}
        try:
            await self._make_request(
                "POST",
                f"/organizations/{auth0_org_id}/enabled_connections",
                json_data=body,
            )
        except Exception as e:
            logger.error(
                f"Auth0 API error adding connection {connection_id} to org {auth0_org_id}: {e}"
            )
            raise


# ---------------------------------------------------------------------------
# Module-level singleton (created only when auth is enabled)
# ---------------------------------------------------------------------------

auth0_management_client: Optional[Auth0ManagementClient] = None
if settings.AUTH_ENABLED:
    auth0_management_client = Auth0ManagementClient()


# ---------------------------------------------------------------------------
# IdentityProvider adapter
# ---------------------------------------------------------------------------


class Auth0IdentityProvider(IdentityProvider):
    """Implements IdentityProvider via Auth0 Management API.

    Maps Auth0/httpx errors to protocol-level exceptions so domain
    code only depends on ``IdentityProviderError`` and its subclasses.
    """

    def __init__(self, client: Auth0ManagementClient) -> None:
        """Initialize Auth0IdentityProvider."""
        self._client = client

    @staticmethod
    def _map_error(e: Exception) -> IdentityProviderError:
        """Convert an Auth0/httpx exception to a protocol exception."""
        if isinstance(e, Auth0RateLimitError):
            return IdentityProviderRateLimitError(str(e), retry_after=e.retry_after)
        if isinstance(e, httpx.HTTPStatusError):
            status = e.response.status_code
            if status == 404:
                return IdentityProviderNotFoundError(str(e))
            if status == 409:
                return IdentityProviderConflictError(str(e))
        if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
            return IdentityProviderUnavailableError(str(e))
        return IdentityProviderError(str(e))

    # --- Organization lifecycle ---

    async def create_organization(self, name: str, display_name: str) -> Optional[dict]:
        """Create organization via Auth0 Management API."""
        try:
            return await self._client.create_organization(name=name, display_name=display_name)
        except Exception as e:
            raise self._map_error(e) from e

    async def delete_organization(self, org_id: str) -> None:
        """Delete organization via Auth0 Management API."""
        try:
            await self._client.delete_organization(org_id)
        except Exception as e:
            raise self._map_error(e) from e

    # --- Organization setup ---

    async def get_all_connections(self) -> list[dict]:
        """Return all authentication connections from Auth0."""
        try:
            return await self._client.get_all_connections()
        except Exception as e:
            raise self._map_error(e) from e

    async def add_enabled_connection(self, org_id: str, connection_id: str) -> None:
        """Enable a connection for an organization in Auth0."""
        try:
            await self._client.add_enabled_connection_to_organization(org_id, connection_id)
        except Exception as e:
            raise self._map_error(e) from e

    # --- User-org relationships ---

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """Add a user to an organization in Auth0."""
        try:
            await self._client.add_user_to_organization(org_id, user_id)
        except Exception as e:
            raise self._map_error(e) from e

    async def remove_user_from_organization(self, org_id: str, user_id: str) -> None:
        """Remove a user from an organization in Auth0."""
        try:
            await self._client.remove_user_from_organization(org_id, user_id)
        except Exception as e:
            raise self._map_error(e) from e

    async def get_user_organizations(self, user_id: str) -> list[dict]:
        """Return organizations the user belongs to in Auth0."""
        try:
            return await self._client.get_user_organizations(user_id)
        except Exception as e:
            raise self._map_error(e) from e

    async def get_member_roles(self, org_id: str, user_id: str) -> list[dict]:
        """Return roles for a member of an organization in Auth0."""
        try:
            return await self._client.get_organization_member_roles(org_id, user_id)
        except Exception as e:
            raise self._map_error(e) from e

    # --- Invitations ---

    async def invite_user(self, org_id: str, email: str, role: str, inviter: Any) -> dict:
        """Send an organization invitation via Auth0."""
        try:
            return await self._client.invite_user_to_organization(
                org_id, email, role, inviter_user=inviter
            )
        except Exception as e:
            raise self._map_error(e) from e

    async def get_pending_invitations(self, org_id: str) -> list[dict]:
        """Return pending invitations for an organization from Auth0."""
        try:
            return await self._client.get_pending_invitations(org_id)
        except Exception as e:
            raise self._map_error(e) from e

    async def delete_invitation(self, org_id: str, invitation_id: str) -> None:
        """Delete a pending invitation in Auth0."""
        try:
            await self._client.delete_invitation(org_id, invitation_id)
        except Exception as e:
            raise self._map_error(e) from e

    # --- System lookups ---

    async def get_roles(self) -> list[dict]:
        """Return all available roles from Auth0."""
        try:
            return await self._client.get_roles()
        except Exception as e:
            raise self._map_error(e) from e
