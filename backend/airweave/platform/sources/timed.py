"""Timed source implementation for testing sync lifecycle.

Generates N entities spread evenly over a configurable duration in seconds.
Designed for deterministic, timing-sensitive tests (cancellation, state transitions)
without any external API dependencies.
"""

import asyncio
import random
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from airweave.platform.configs.auth import TimedAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.timed import TimedContainerEntity, TimedEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Word lists for deterministic content generation
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
]

ADJECTIVES = [
    "important",
    "urgent",
    "detailed",
    "comprehensive",
    "preliminary",
    "final",
    "quarterly",
    "annual",
    "weekly",
    "daily",
]

VERBS = [
    "created",
    "updated",
    "reviewed",
    "completed",
    "started",
    "assigned",
    "submitted",
    "approved",
    "rejected",
    "archived",
]


@source(
    name="Timed",
    short_name="timed",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="TimedAuthConfig",
    config_class="TimedConfig",
    labels=["Internal", "Testing"],
    supports_continuous=False,
    internal=True,
)
class TimedSource(BaseSource):
    """Timed source connector for testing sync lifecycle.

    Generates N entities spread evenly over a configurable duration.
    No external API calls are made - all content is generated locally.
    This is designed for precise timing control in cancellation and
    state transition tests.
    """

    def __init__(self):
        """Initialize the timed source."""
        super().__init__()
        self.seed: int = 42
        self.entity_count: int = 100
        self.duration_seconds: float = 10.0
        self._rng: Optional[random.Random] = None

    @classmethod
    async def create(
        cls,
        credentials: Optional[TimedAuthConfig] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "TimedSource":
        """Create a new timed source instance.

        Args:
            credentials: Optional auth config (not used for timed source).
            config: Source configuration parameters including:
                - entity_count: Number of entities to generate (default: 100)
                - duration_seconds: Total time to generate all entities (required)
                - seed: Random seed for reproducible content (default: 42)

        Returns:
            Configured TimedSource instance.
        """
        instance = cls()
        config = config or {}

        instance.seed = config.get("seed", 42)
        instance.entity_count = config.get("entity_count", 100)
        instance.duration_seconds = config.get("duration_seconds", 10.0)

        instance._rng = random.Random(instance.seed)

        return instance

    def _generate_title(self, index: int) -> str:
        """Generate a deterministic title for an entity."""
        adj = ADJECTIVES[index % len(ADJECTIVES)]
        noun = NOUNS[index % len(NOUNS)]
        return f"{adj.capitalize()} {noun} #{index + 1}"

    def _generate_content(self, index: int) -> str:
        """Generate deterministic content for an entity."""
        verb = VERBS[index % len(VERBS)]
        noun = NOUNS[index % len(NOUNS)]
        adj = ADJECTIVES[(index + 3) % len(ADJECTIVES)]
        seed_phrase = f"seed-{self.seed}"

        return (
            f"This {adj} {noun} was {verb} as part of timed test generation "
            f"({seed_phrase}). Entity {index + 1} of {self.entity_count}, "
            f"generated over {self.duration_seconds} seconds. "
            f"The content is deterministic and reproducible for testing purposes."
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate timed entities spread evenly over the configured duration.

        Yields:
            BaseEntity instances at regular intervals.
        """
        self.logger.info(
            f"TimedSource: generating {self.entity_count} entities "
            f"over {self.duration_seconds}s (seed={self.seed})"
        )

        # Calculate delay between entities
        if self.entity_count > 1:
            delay_per_entity = self.duration_seconds / self.entity_count
        else:
            delay_per_entity = 0.0

        # First yield the container entity
        container_id = f"timed-container-{self.seed}"
        container = TimedContainerEntity(
            container_id=container_id,
            container_name=f"Timed Container (seed={self.seed})",
            description=(
                f"Timed test container: {self.entity_count} entities over {self.duration_seconds}s"
            ),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            breadcrumbs=[],
        )
        yield container

        # Create breadcrumb from container
        container_breadcrumb = Breadcrumb(
            entity_id=container_id,
            name=container.container_name,
            entity_type="TimedContainerEntity",
        )

        # Generate entities with delay
        for i in range(self.entity_count):
            entity = TimedEntity(
                entity_id=f"timed-{self.seed}-{i}",
                name=self._generate_title(i),
                content=self._generate_content(i),
                sequence_number=i,
                created_at=datetime(2024, 1, 1, 0, 0, i % 60),
                breadcrumbs=[container_breadcrumb],
            )
            yield entity

            # Sleep between entities (except after the last one)
            if delay_per_entity > 0 and i < self.entity_count - 1:
                await asyncio.sleep(delay_per_entity)

        self.logger.info(f"TimedSource: finished generating {self.entity_count} entities")

    async def validate(self) -> bool:
        """Validate the timed source (always succeeds)."""
        return True
