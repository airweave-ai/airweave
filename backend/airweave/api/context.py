"""HTTP API request context.

Extends BaseContext with request-specific fields: authentication metadata,
request tracking, user identity, and analytics.
Only the API layer creates these via deps.get_context().
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.logging import logger as root_logger
from airweave.core.shared_models import AuthMethod


class RequestHeaders(BaseModel):
    """Structured representation of tracking-relevant request headers."""

    # Standard headers
    user_agent: Optional[str] = None

    # Client/Frontend headers
    client_name: Optional[str] = None
    client_version: Optional[str] = None
    session_id: Optional[str] = None

    # SDK headers
    sdk_name: Optional[str] = None
    sdk_version: Optional[str] = None

    # Fern-specific headers
    fern_language: Optional[str] = None
    fern_runtime: Optional[str] = None
    fern_runtime_version: Optional[str] = None

    # Agent framework headers
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None

    # Request tracking
    request_id: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for PostHog properties, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


@dataclass
class ApiContext(BaseContext):
    """Full HTTP request context.

    Inherits organization, logger, and feature-flag helpers from BaseContext.
    Adds user identity, request metadata, auth info, and analytics.

    Created by deps.get_context() and injected into endpoints via Depends().
    """

    # User identity (only present for Auth0/system auth, None for API keys)
    user: Optional[schemas.User] = None

    # Request metadata
    request_id: str = ""

    # Authentication context
    auth_method: AuthMethod = AuthMethod.SYSTEM
    auth_metadata: Optional[Dict[str, Any]] = None

    # Request headers for analytics enrichment
    headers: Optional[RequestHeaders] = field(default=None, repr=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- User property overrides ---

    @property
    def has_user_context(self) -> bool:
        """Whether this context has user info (for audit tracking)."""
        return self.user is not None

    @property
    def tracking_email(self) -> Optional[str]:
        """Email for created_by/modified_by audit fields."""
        return self.user.email if self.user else None

    @property
    def user_id(self) -> Optional[UUID]:
        """User ID if available."""
        return self.user.id if self.user else None

    # --- API-specific helpers ---

    @property
    def is_api_key_auth(self) -> bool:
        """Whether this is API key authentication."""
        return self.auth_method == AuthMethod.API_KEY

    @property
    def is_user_auth(self) -> bool:
        """Whether this is user authentication (Auth0)."""
        return self.auth_method == AuthMethod.AUTH0

    @classmethod
    def for_system(
        cls,
        organization: schemas.Organization,
        source: str = "system",
    ) -> "ApiContext":
        """Create a system context for internal/background operations.

        Args:
            organization: The organization to create context for.
            source: Identifier for the subsystem creating the context.
        """
        request_id = str(uuid4())
        return cls(
            request_id=request_id,
            auth_method=AuthMethod.INTERNAL_SYSTEM,
            organization=organization,
            user=None,
            logger=root_logger.with_context(
                request_id=request_id,
                organization_id=str(organization.id),
                auth_method=AuthMethod.INTERNAL_SYSTEM.value,
                source=source,
            ),
        )

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


@dataclass
class ConnectContext(BaseContext):
    """Context for Connect session-authenticated requests.

    Not an ApiContext — connect sessions have no user, no Auth0 token,
    and a different auth lifecycle (HMAC session token scoped to a
    collection).  Extends BaseContext directly.

    Downstream services type-hint ApiContext but only read BaseContext
    fields (organization, logger).  ConnectContext satisfies that contract
    structurally; broadening those hints to BaseContext is a separate task.

    Headers carry ``client_name="airweave-connect"`` so analytics (PostHog)
    can identify connect traffic once wired.
    """

    # Request tracking
    request_id: str = ""

    # Connect session identity
    session_id: UUID = field(default_factory=uuid4)
    collection_id: str = ""
    end_user_id: Optional[str] = None
    allowed_integrations: Optional[List[str]] = None
    mode: str = "all"

    # Stored so downstream code that reads auth_metadata keeps working
    auth_method: AuthMethod = AuthMethod.API_KEY
    auth_metadata: Optional[Dict[str, Any]] = None

    # Analytics tracking headers
    headers: Optional[RequestHeaders] = field(default=None, repr=False)

    @classmethod
    def from_session(
        cls,
        *,
        organization: schemas.Organization,
        session_id: UUID,
        collection_id: str,
        end_user_id: Optional[str] = None,
        allowed_integrations: Optional[List[str]] = None,
        mode: str = "all",
    ) -> "ConnectContext":
        """Build a ConnectContext from decoded session fields + resolved org."""
        request_id = str(uuid4())
        return cls(
            organization=organization,
            request_id=request_id,
            session_id=session_id,
            collection_id=collection_id,
            end_user_id=end_user_id,
            allowed_integrations=allowed_integrations,
            mode=mode,
            auth_method=AuthMethod.API_KEY,
            auth_metadata={
                "connect_session_id": str(session_id),
                "end_user_id": end_user_id,
            },
            headers=RequestHeaders(
                client_name="airweave-connect",
                session_id=str(session_id),
                request_id=request_id,
            ),
            logger=root_logger.with_context(
                request_id=request_id,
                session_id=str(session_id),
                organization_id=str(organization.id),
                context_base="connect_session",
                **({"end_user_id": end_user_id} if end_user_id else {}),
            ),
        )

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"ConnectContext(request_id={self.request_id[:8]}..., "
            f"session={self.session_id}, "
            f"collection={self.collection_id}, "
            f"org={self.organization.id})"
        )
