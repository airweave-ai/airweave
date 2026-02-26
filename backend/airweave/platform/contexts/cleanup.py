"""Cleanup context for deletion operations."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List
from uuid import UUID

from airweave.core.context import BaseContext

if TYPE_CHECKING:
    from airweave.platform.destinations._base import BaseDestination


@dataclass
class CleanupContext(BaseContext):
    """Minimal context for cleanup/deletion operations.

    Inherits organization and logger from BaseContext.
    Can be passed directly as ctx to CRUD operations.
    """

    sync_id: UUID
    collection_id: UUID
    source_connection_id: UUID
    destinations: List["BaseDestination"] = field(default_factory=list)

    @property
    def organization_id(self) -> UUID:
        """Organization ID from inherited BaseContext."""
        return self.organization.id

    @property
    def destination_list(self) -> List["BaseDestination"]:
        """Alias for destinations."""
        return self.destinations

    @property
    def ctx(self) -> "BaseContext":
        """Self-reference for backwards compat during migration."""
        return self
