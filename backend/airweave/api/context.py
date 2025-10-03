"""Unified application context for API requests.

This module provides a comprehensive context object that combines authentication,
logging, and request metadata into a single injectable dependency.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from airweave import schemas
from airweave.core.logging import ContextualLogger
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
    auth_method: str  # "auth0", "api_key", "system"
    auth_metadata: Optional[Dict[str, Any]] = None

    # Contextual logger with all dimensions pre-configured
    logger: ContextualLogger

    # Analytics service with context and headers pre-configured
    analytics: Optional[Any] = (
        None  # ContextualAnalyticsService - using Any to avoid circular imports
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True  # For ContextualLogger

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
        return self.auth_method == "api_key"

    @property
    def is_user_auth(self) -> bool:
        """Whether this is user authentication (Auth0)."""
        return self.auth_method == "auth0"

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
                f"method={self.auth_method}, user={self.user.email}, "
                f"org={self.organization.id})"
            )
        else:
            return (
                f"ApiContext(request_id={self.request_id[:8]}..., "
                f"method={self.auth_method}, org={self.organization.id})"
            )

    def to_serializable_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dictionary.

        Returns:
            Dict containing all fields
        """
        return {
            "request_id": self.request_id,
            "organization_id": str(self.organization.id),
            "organization": self.organization.model_dump(mode="json"),
            "user": self.user.model_dump(mode="json") if self.user else None,
            "auth_method": self.auth_method,
            "auth_metadata": self.auth_metadata,
        }
