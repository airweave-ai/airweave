"""Protocols for registries."""

from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict


class BaseRegistryEntry(BaseModel):
    """Registry entry."""

    model_config = ConfigDict(frozen=True)

    short_name: str
    name: str
    description: str | None
    class_name: str


EntryT = TypeVar("EntryT", bound=BaseRegistryEntry, covariant=True)


class RegistryProtocol(Protocol[EntryT]):
    """Base protocol for in-memory registries.

    Built once at startup. All lookups are synchronous dict reads.
    """

    def get(self, short_name: str) -> EntryT:
        """Get an entry by short name. Raises KeyError if not found."""
        ...

    def list_all(self) -> list[EntryT]:
        """List all registered entries."""
        ...
