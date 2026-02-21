"""Base context for all operations.

Provides the universal context type that all specialized contexts inherit from.
CRUD layer and services type-hint against BaseContext. Specialized contexts
(ApiContext, SyncContext, CleanupContext) extend it with domain-specific fields.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID

from airweave import schemas

if TYPE_CHECKING:
    from airweave.core.logging import ContextualLogger
    from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum


@dataclass
class BaseContext:
    """Base context for all operations.

    Carries organization identity for CRUD access control and a contextual
    logger with identity dimensions. All specialized contexts inherit from this.

    The only __init__ field is ``organization`` (no defaults), so subclasses
    can freely add required fields without dataclass ordering conflicts.

    Logger is auto-derived from organization in __post_init__. Override it
    after construction when a richer logger is needed (e.g. with sync_id).
    """

    organization: schemas.Organization

    logger: "ContextualLogger" = field(init=False, repr=False)

    def __post_init__(self):
        """Auto-derive logger from organization identity."""
        from airweave.core.logging import logger as base_logger

        dims: Dict[str, str] = {
            "organization_id": str(self.organization.id),
            "organization_name": self.organization.name,
        }
        self.logger = base_logger.with_context(**dims)

    # --- Properties used by CRUD base class (_base_organization.py) ---

    @property
    def has_user_context(self) -> bool:
        """Whether this context has user info (for audit tracking)."""
        return False

    @property
    def tracking_email(self) -> Optional[str]:
        """Email for created_by/modified_by audit fields."""
        return None

    @property
    def user_id(self) -> Optional[UUID]:
        """User ID if available."""
        return None

    def has_feature(self, flag: "FeatureFlagEnum") -> bool:
        """Check if organization has a feature enabled.

        Args:
            flag: Feature flag to check (use FeatureFlag enum from core.shared_models)

        Returns:
            True if enabled, False otherwise
        """
        return flag in self.organization.enabled_features
