"""HTTP API request context.

Extends BaseContext with request-specific fields: authentication metadata,
request tracking, and analytics. Only the API layer creates these via deps.get_context().
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pydantic import ConfigDict

from airweave.core.context import BaseContext
from airweave.core.shared_models import AuthMethod


@dataclass
class ApiContext(BaseContext):
    """Full HTTP request context.

    Inherits organization, user, logger, and identity properties from BaseContext.
    Adds request-specific fields that only the API layer needs.

    Created by deps.get_context() and injected into endpoints via Depends().
    """

    # Request metadata
    request_id: str = ""

    # Authentication context
    auth_method: AuthMethod = AuthMethod.SYSTEM
    auth_metadata: Optional[Dict[str, Any]] = None

    # Analytics service with context and headers pre-configured
    analytics: Optional[Any] = field(default=None, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def is_api_key_auth(self) -> bool:
        """Whether this is API key authentication."""
        return self.auth_method == AuthMethod.API_KEY

    @property
    def is_user_auth(self) -> bool:
        """Whether this is user authentication (Auth0)."""
        return self.auth_method == AuthMethod.AUTH0

    def to_serializable_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dictionary for Temporal workflow payloads.

        Returns:
            Dict containing all fields needed to reconstruct context in activities.
        """
        from airweave.core.config import settings

        return {
            "request_id": self.request_id,
            "organization_id": str(self.organization.id),
            "organization": self.organization.model_dump(mode="json"),
            "user": self.user.model_dump(mode="json") if self.user else None,
            "auth_method": self.auth_method.value,
            "auth_metadata": self.auth_metadata,
            "local_development": settings.LOCAL_DEVELOPMENT,
        }

    def __str__(self) -> str:
        """String representation for logging."""
        if self.user:
            return (
                f"ApiContext(request_id={self.request_id[:8]}..., "
                f"method={self.auth_method.value}, user={self.user.email}, "
                f"org={self.organization.id})"
            )
        return (
            f"ApiContext(request_id={self.request_id[:8]}..., "
            f"method={self.auth_method.value}, org={self.organization.id})"
        )
