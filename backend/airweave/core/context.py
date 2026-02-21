"""Base context for all operations.

Provides the universal context type that all specialized contexts inherit from.
CRUD layer and services type-hint against BaseContext. Specialized contexts
(ApiContext, SyncContext, CleanupContext) extend it with domain-specific fields.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID

from airweave import schemas
from airweave.core.logging import ContextualLogger

if TYPE_CHECKING:
    from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum


@dataclass
class BaseContext:
    """Base context for all operations.

    Carries organization identity for CRUD access control and a contextual
    logger with identity dimensions. All specialized contexts inherit from this.

    ``organization`` is the only positional __init__ field (no default), so
    subclasses can freely add required fields without dataclass ordering
    conflicts. ``logger`` is keyword-only with a default of None; when
    omitted it is auto-derived from the organization in __post_init__.
    """

    organization: schemas.Organization

    logger: ContextualLogger = field(default=None, kw_only=True, repr=False)

    def __post_init__(self):
        """Auto-derive logger from organization identity if not provided."""
        if self.logger is None:
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
