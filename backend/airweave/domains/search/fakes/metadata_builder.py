"""In-memory fake for CollectionMetadataBuilderProtocol."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.search.protocols import CollectionMetadataBuilderProtocol
from airweave.domains.search.types import CollectionMetadata
from airweave.domains.search.types.metadata import SourceMetadata


class FakeCollectionMetadataBuilder(CollectionMetadataBuilderProtocol):
    """Returns seeded or empty CollectionMetadata. Records calls."""

    def __init__(self) -> None:
        self._result: CollectionMetadata | None = None
        self._calls: list[tuple] = []

    def seed_result(self, result: CollectionMetadata) -> None:
        self._result = result

    async def build(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: str,
    ) -> CollectionMetadata:
        self._calls.append(("build", collection_readable_id))
        if self._result is not None:
            return self._result
        return CollectionMetadata(
            collection_id="fake-id",
            collection_readable_id=collection_readable_id,
            sources=[
                SourceMetadata(
                    short_name="stub",
                    description="Test source",
                    entity_types=[],
                    federated=False,
                )
            ],
        )
