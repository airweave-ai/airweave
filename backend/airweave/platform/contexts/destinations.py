"""Destinations context for sync operations."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List
from uuid import UUID

if TYPE_CHECKING:
    from airweave.platform.destinations._base import BaseDestination
    from airweave.platform.entities._base import BaseEntity


@dataclass
class DestinationsContext:
    """Everything needed for destination operations.

    Attributes:
        destinations: List of configured destination instances
        entity_map: Mapping of entity class to entity_definition_id
    """

    destinations: List["BaseDestination"] = field(default_factory=list)
    entity_map: Dict[type["BaseEntity"], UUID] = field(default_factory=dict)
