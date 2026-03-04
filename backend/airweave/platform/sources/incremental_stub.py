"""Incremental stub source for testing continuous/incremental sync.

Generates deterministic test entities with cursor-based incremental support.
On first sync, generates all entities. On subsequent syncs, only generates
entities beyond the cursor position. The entity_count can be increased via
config update to simulate new data appearing between syncs.
"""

import random
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from airweave.platform.configs.auth import StubAuthConfig
from airweave.platform.configs.config import IncrementalStubConfig
from airweave.platform.cursors import IncrementalStubCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.stub import SmallStubEntity, StubContainerEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Word lists for deterministic content generation (subset from stub.py)
NOUNS = [
    "project",
    "task",
    "document",
    "report",
    "meeting",
    "analysis",
    "review",
    "strategy",
    "plan",
    "update",
    "milestone",
    "feature",
]
ADJECTIVES = [
    "important",
    "urgent",
    "critical",
    "minor",
    "major",
    "quick",
    "detailed",
    "comprehensive",
    "preliminary",
    "final",
    "draft",
    "approved",
]
AUTHORS = [
    "Alice Smith",
    "Bob Johnson",
    "Charlie Brown",
    "Diana Prince",
    "Eve Wilson",
]


@source(
    name="Incremental Stub",
    short_name="incremental_stub",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=StubAuthConfig,
    config_class=IncrementalStubConfig,
    labels=["Internal", "Testing"],
    supports_continuous=True,
    cursor_class=IncrementalStubCursor,
    internal=True,
)
class IncrementalStubSource(BaseSource):
    """Incremental stub source for testing continuous sync.

    Generates deterministic SmallStubEntity instances with cursor-based
    incremental support. On first sync (no cursor), generates all entities.
    On subsequent syncs, only generates entities beyond the last cursor position.
    """

    def __init__(self):
        """Initialize the incremental stub source."""
        super().__init__()
        self.seed: int = 42
        self.entity_count: int = 5

    @classmethod
    async def create(
        cls,
        credentials: Optional[StubAuthConfig] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "IncrementalStubSource":
        """Create a new incremental stub source instance."""
        instance = cls()
        config = config or {}
        instance.seed = config.get("seed", 42)
        instance.entity_count = config.get("entity_count", 5)
        return instance

    def _generate_entity(self, index: int, breadcrumbs: list[Breadcrumb]) -> SmallStubEntity:
        """Generate a deterministic SmallStubEntity for the given index."""
        rng = random.Random(self.seed + index)
        title = f"{rng.choice(ADJECTIVES).capitalize()} {rng.choice(NOUNS)} #{index}"
        content = f"Incremental stub entity {index} (seed={self.seed}). "
        content += " ".join(f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}" for _ in range(5))
        return SmallStubEntity(
            stub_id=f"inc-stub-{self.seed}-{index}",
            title=title,
            content=content,
            author=rng.choice(AUTHORS),
            tags=[rng.choice(NOUNS) for _ in range(2)],
            created_at=datetime(2024, 1, 1 + (index % 28), index % 24, 0, 0),
            modified_at=datetime(2024, 2, 1 + (index % 28), index % 24, 0, 0),
            sequence_number=index,
            breadcrumbs=breadcrumbs,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities with incremental cursor support.

        First sync: yields container + all entities, sets cursor to last index.
        Incremental sync: yields container + only new entities beyond cursor.
        """
        cursor_data = self.cursor.data if self.cursor else {}
        last_index = cursor_data.get("last_entity_index", -1)
        is_incremental = last_index >= 0

        if is_incremental:
            self.logger.info(
                f"Incremental sync: cursor last_entity_index={last_index}, "
                f"current entity_count={self.entity_count}"
            )
            start_index = last_index + 1
        else:
            self.logger.info(
                f"Full sync: generating {self.entity_count} entities (seed={self.seed})"
            )
            start_index = 0

        # Always yield the container entity
        container_id = f"inc-stub-container-{self.seed}"
        container = StubContainerEntity(
            container_id=container_id,
            container_name=f"Incremental Stub Container (seed={self.seed})",
            description=f"Incremental test container with {self.entity_count} entities",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            seed=self.seed,
            entity_count=self.entity_count,
            breadcrumbs=[],
        )
        yield container

        container_breadcrumb = Breadcrumb(
            entity_id=container_id,
            name=container.container_name,
            entity_type="StubContainerEntity",
        )
        breadcrumbs = [container_breadcrumb]

        # Generate entities from start_index to entity_count
        new_count = 0
        for i in range(start_index, self.entity_count):
            entity = self._generate_entity(i, breadcrumbs)
            yield entity
            new_count += 1

        self.logger.info(
            f"Generated {new_count} entities (indices {start_index}-{self.entity_count - 1})"
        )

        # Update cursor
        if self.cursor and self.entity_count > 0:
            self.cursor.update(
                last_entity_index=self.entity_count - 1,
                entity_count=self.entity_count,
            )

    async def validate(self) -> bool:
        """Validate the incremental stub source configuration.

        Always returns True since stub source doesn't require external validation.
        """
        return True
