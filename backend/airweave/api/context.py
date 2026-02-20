"""Unified application context for API requests.

This module provides a comprehensive context object that combines authentication,
logging, and request metadata into a single injectable dependency.
"""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from airweave import schemas
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as root_logger
from airweave.core.shared_models import AuthMethod
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum


class ApiContext(BaseModel):
    """Unified context for API requests.

    Combines authentication, logging, and request metadata into a single
    context object that can be injected into endpoints via FastAPI dependencies.
    This context is specifically for HTTP API requests, not background jobs or syncs.
    """

    # Request metadata
    request_id: str

    # Authentication context
    organization: schemas.Organization
    user: Optional[schemas.User] = None
    auth_method: AuthMethod
    auth_metadata: Optional[Dict[str, Any]] = None

    # Contextual logger with all dimensions pre-configured
    logger: ContextualLogger

    # Analytics service with context and headers pre-configured
    analytics: Optional[Any] = (
        None  # ContextualAnalyticsService - using Any to avoid circular imports
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def has_user_context(self) -> bool:
        """Whether this context has user info for tracking."""
        return self.user is not None

    @property
    def tracking_email(self) -> Optional[str]:
        """Email to use for UserMixin tracking."""
        return self.user.email if self.user else None

    @property
    def user_id(self) -> Optional[UUID]:
        """User ID if available."""
        return self.user.id if self.user else None

    @property
    def is_api_key_auth(self) -> bool:
        """Whether this is API key authentication."""
        return self.auth_method == AuthMethod.API_KEY

    @property
    def is_user_auth(self) -> bool:
        """Whether this is user authentication (Auth0)."""
        return self.auth_method == AuthMethod.AUTH0

    def has_feature(self, flag: FeatureFlagEnum) -> bool:
        """Check if organization has a feature enabled.

        Args:
            flag: Feature flag to check (use FeatureFlag enum from core.shared_models)

        Returns:
            True if enabled, False otherwise

        Example:
            from airweave.core.shared_models import FeatureFlag
            if ctx.has_feature(FeatureFlag.S3_DESTINATION):
                # Feature is enabled for this organization
        """
        return flag in self.organization.enabled_features

    def __str__(self) -> str:
        """String representation for logging."""
        if self.user:
            return (
                f"ApiContext(request_id={self.request_id[:8]}..., "
                f"method={self.auth_method.value}, user={self.user.email}, "
                f"org={self.organization.id})"
            )
        else:
            return (
                f"ApiContext(request_id={self.request_id[:8]}..., "
                f"method={self.auth_method.value}, org={self.organization.id})"
            )

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
        """Convert to a serializable dictionary.

        Returns:
            Dict containing all fields
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
