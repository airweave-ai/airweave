from typing import Protocol

from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.entities.types import EntityDefinitionEntry


class EntityDefinitionRegistryProtocol(RegistryProtocol[EntityDefinitionEntry], Protocol):
    """Entity definition registry protocol."""

    def list_for_source(self, source_short_name: str) -> list[EntityDefinitionEntry]:
        """List all entity definitions for a given source."""
        ...
