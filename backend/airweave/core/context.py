"""Base context for all operations.

Provides the universal context type that all specialized contexts inherit from.
CRUD layer and services type-hint against BaseContext. Specialized contexts
(ApiContext, SyncContext, CleanupContext) extend it with domain-specific fields.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID

if TYPE_CHECKING:
    from airweave import schemas
    from airweave.core.logging import ContextualLogger
    from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum


@dataclass
class BaseContext:
    """Base context for all operations.

    Carries organization identity for CRUD access control and a contextual
    logger with identity dimensions. All specialized contexts inherit from this.

    The logger auto-derives from organization/user if not explicitly provided.
    - API layer overrides with richer logger (request_id, session_id).
    - Sync engine overrides with sync-specific logger (sync_id, job_id).
    - System operations accept the auto-derived default.
    """

    organization: "schemas.Organization"
    user: Optional["schemas.User"] = None
    logger: "ContextualLogger" = field(default=None, repr=False)

    def __post_init__(self):
        """Auto-derive logger from identity if not explicitly provided."""
        if self.logger is None:
            from airweave.core.logging import logger as base_logger

            dims: Dict[str, str] = {
                "organization_id": str(self.organization.id),
                "organization_name": self.organization.name,
            }
            if self.user:
                dims["user_id"] = str(self.user.id)
                dims["user_email"] = self.user.email
            self.logger = base_logger.with_context(**dims)

    # --- Properties used by CRUD base class (_base_organization.py) ---

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

    def has_feature(self, flag: "FeatureFlagEnum") -> bool:
        """Check if organization has a feature enabled.

        Args:
            flag: Feature flag to check (use FeatureFlag enum from core.shared_models)

        Returns:
            True if enabled, False otherwise
        """
        return flag in self.organization.enabled_features
