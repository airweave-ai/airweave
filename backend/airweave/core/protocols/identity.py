"""Identity provider protocol for organization and user management.

Abstracts the external identity system (Auth0, etc.) so domain code
never imports infrastructure directly. Adapters implement this protocol;
domains depend only on the protocol type.
"""

from typing import Any, Optional, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Abstract exceptions — domain code catches these, adapters raise them
# ---------------------------------------------------------------------------


class IdentityProviderError(Exception):
    """Base for all identity provider failures."""

    def __init__(self, message: str = "Identity provider error"):
        """Initialize IdentityProviderError."""
        self.message = message
        super().__init__(message)


class IdentityProviderRateLimitError(IdentityProviderError):
    """Provider is throttling requests (retryable after *retry_after* seconds)."""

    def __init__(
        self,
        message: str = "Identity provider rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        """Initialize IdentityProviderRateLimitError."""
        self.retry_after = retry_after
        super().__init__(message)


class IdentityProviderUnavailableError(IdentityProviderError):
    """Provider is down or unreachable (retryable)."""

    def __init__(self, message: str = "Identity provider unavailable"):
        """Initialize IdentityProviderUnavailableError."""
        super().__init__(message)


class IdentityProviderConflictError(IdentityProviderError):
    """Duplicate resource (org already exists, user already a member, etc.)."""

    def __init__(self, message: str = "Identity provider conflict"):
        """Initialize IdentityProviderConflictError."""
        super().__init__(message)


class IdentityProviderNotFoundError(IdentityProviderError):
    """Resource doesn't exist in the identity provider."""

    def __init__(self, message: str = "Identity provider resource not found"):
        """Initialize IdentityProviderNotFoundError."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class IdentityProvider(Protocol):
    """External identity/org management system (Auth0, etc.).

    Methods are grouped by capability. The NullIdentityProvider adapter
    provides no-ops for AUTH_ENABLED=false environments.

    All methods may raise subclasses of ``IdentityProviderError``.
    """

    # --- Organization lifecycle ---

    async def create_organization(self, name: str, display_name: str) -> Optional[dict]:
        """Create an organization in the identity provider.

        Returns:
            Organization data dict with at least an ``"id"`` key,
            or ``None`` when identity management is disabled.
        """
        ...

    async def delete_organization(self, org_id: str) -> None:
        """Delete an organization from the identity provider."""
        ...

    # --- Organization setup ---

    async def get_all_connections(self) -> list[dict]:
        """Return all available authentication connections."""
        ...

    async def add_enabled_connection(self, org_id: str, connection_id: str) -> None:
        """Enable an authentication connection for an organization."""
        ...

    # --- User-org relationships ---

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """Add a user to an organization."""
        ...

    async def remove_user_from_organization(self, org_id: str, user_id: str) -> None:
        """Remove a user from an organization."""
        ...

    async def get_user_organizations(self, user_id: str) -> list[dict]:
        """Return organizations the user belongs to."""
        ...

    async def get_member_roles(self, org_id: str, user_id: str) -> list[dict]:
        """Return the roles assigned to a specific member of an organization."""
        ...

    # --- Invitations ---

    async def invite_user(self, org_id: str, email: str, role: str, inviter: Any) -> dict:
        """Send an invitation to join an organization.

        Returns:
            Invitation data dict (at least ``"id"`` and ``"created_at"``).
        """
        ...

    async def get_pending_invitations(self, org_id: str) -> list[dict]:
        """Return pending invitations for an organization."""
        ...

    async def delete_invitation(self, org_id: str, invitation_id: str) -> None:
        """Delete a pending invitation."""
        ...

    # --- System lookups ---

    async def get_roles(self) -> list[dict]:
        """Return all available roles in the identity system."""
        ...
