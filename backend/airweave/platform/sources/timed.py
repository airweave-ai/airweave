"""Timed source implementation for testing sync lifecycle.

Generates N entities spread evenly over a configurable duration in seconds.
Designed for deterministic, timing-sensitive tests (cancellation, state transitions)
without any external API dependencies.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import TimedAuthConfig
from airweave.platform.configs.config import TimedConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.timed import TimedContainerEntity, TimedEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

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
    auth_config_class=TimedAuthConfig,
    config_class=TimedConfig,
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

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: TimedConfig,
    ) -> TimedSource:
        """Create a TimedSource configured from the given config."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.seed = config.seed
        instance.entity_count = config.entity_count
        instance.duration_seconds = config.duration_seconds
        instance._rng = random.Random(instance.seed)  # noqa: S311
        return instance

    def _generate_title(self, index: int) -> str:
        adj = ADJECTIVES[index % len(ADJECTIVES)]
        noun = NOUNS[index % len(NOUNS)]
        return f"{adj.capitalize()} {noun} #{index + 1}"

    def _generate_content(self, index: int) -> str:
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

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield timed entities with configurable delays between each."""
        self.logger.info(
            f"TimedSource: generating {self.entity_count} entities "
            f"over {self.duration_seconds}s (seed={self.seed})"
        )

        if self.entity_count > 1:
            delay_per_entity = self.duration_seconds / self.entity_count
        else:
            delay_per_entity = 0.0

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

        container_breadcrumb = Breadcrumb(
            entity_id=container_id,
            name=container.container_name,
            entity_type="TimedContainerEntity",
        )

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

            if delay_per_entity > 0 and i < self.entity_count - 1:
                await asyncio.sleep(delay_per_entity)

        self.logger.info(f"TimedSource: finished generating {self.entity_count} entities")

    async def validate(self) -> None:
        """Validate the source (always succeeds for timed test sources)."""
