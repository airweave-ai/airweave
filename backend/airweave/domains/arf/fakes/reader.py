"""In-memory fake for ArfReaderProtocol."""

from typing import Any, AsyncGenerator, Dict, List, Optional

from airweave.domains.arf.protocols import ArfReaderProtocol
from airweave.platform.entities._base import BaseEntity


class FakeArfReader(ArfReaderProtocol):
    """In-memory fake for ArfReaderProtocol.

    Returns pre-seeded entities and manifest data.
    """

    def __init__(self) -> None:
        self._entities: List[BaseEntity] = []
        self._manifest: Optional[Dict[str, Any]] = None
        self._valid: bool = True
        self._calls: List[tuple] = []
        self._should_raise: Optional[Exception] = None

    # -- Test helpers ----------------------------------------------------------

    def seed_entities(self, entities: List[BaseEntity]) -> None:
        """Pre-populate entities to return during iteration."""
        self._entities = list(entities)

    def seed_manifest(self, manifest: Dict[str, Any]) -> None:
        """Pre-populate the manifest dict."""
        self._manifest = manifest

    def set_valid(self, valid: bool) -> None:
        """Control what validate() returns."""
        self._valid = valid

    def set_error(self, error: Exception) -> None:
        """Configure next call to raise."""
        self._should_raise = error

    def get_calls(self, method: str) -> List[tuple]:
        """Return calls for a specific method."""
        return [c for c in self._calls if c[0] == method]

    # -- Protocol implementation -----------------------------------------------

    async def validate(self) -> bool:
        self._calls.append(("validate",))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return self._valid

    async def read_manifest(self) -> Dict[str, Any]:
        self._calls.append(("read_manifest",))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        if self._manifest is None:
            raise FileNotFoundError("No manifest seeded")
        return self._manifest

    async def get_entity_count(self) -> int:
        self._calls.append(("get_entity_count",))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        return len(self._entities)

    async def iter_entities(self) -> AsyncGenerator[BaseEntity, None]:
        self._calls.append(("iter_entities",))
        if self._should_raise:
            exc, self._should_raise = self._should_raise, None
            raise exc
        for entity in self._entities:
            yield entity

    def cleanup(self) -> None:
        self._calls.append(("cleanup",))
