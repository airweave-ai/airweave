"""Temporal activity for Structural Context Extraction (SCE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from uuid import UUID

from temporalio import activity

from airweave.platform.destinations import VectorDBDestination
from airweave.platform.destinations._base import VectorDBUpdate
from airweave.platform.sce.protocols import StructuralContextExtractorServiceProtocol
from airweave.platform.sce.types import EntityAnnotations, EntityExtractionInput
from airweave.schemas.search_result import AirweaveSearchResult

QUERY_BATCH_SIZE = 10000


@dataclass
class ExtractStructuralContextActivity:
    """Extract structural context (refs) from synced entities.

    Dependencies:
        sce_service: The SCE orchestration service
        destination: VectorDBDestination for querying and updating synced entities
    """

    sce_service: StructuralContextExtractorServiceProtocol
    destination: VectorDBDestination

    @activity.defn(name="extract_structural_context")
    async def run(self, collection_id: str, sync_id: str) -> None:
        """Fetch entities, extract structural refs, and write annotations back.

        Args:
            collection_id: The collection to extract from.
            sync_id: The sync job that produced the entities.
        """
        cid = UUID(collection_id)
        sid = UUID(sync_id)

        offset = 0
        while True:
            docs = await self.destination.query_documents(
                cid, sid, limit=QUERY_BATCH_SIZE, offset=offset
            )
            if not docs:
                break

            annotations = await self._extract_batch(docs)
            updates = self._build_updates(docs, annotations)
            await self.destination.bulk_update(updates)

            if len(docs) < QUERY_BATCH_SIZE:
                break
            offset += QUERY_BATCH_SIZE

    async def _extract_batch(
        self, documents: List[AirweaveSearchResult]
    ) -> List[EntityAnnotations]:
        """Run SCE on a batch of documents."""
        entity_inputs = [
            EntityExtractionInput(entity_id=doc.entity_id, text=doc.textual_representation)
            for doc in documents
            if doc.entity_id and doc.textual_representation
        ]

        annotations: List[EntityAnnotations] = []
        async for ann in self.sce_service.process_entities(entity_inputs):
            annotations.append(ann)

        activity.heartbeat()
        return annotations

    @staticmethod
    def _build_updates(
        docs: List[AirweaveSearchResult],
        annotations: List[EntityAnnotations],
    ) -> List[VectorDBUpdate]:
        """Build update objects from documents and their annotations."""
        ann_by_entity = {ann.entity_id: ann for ann in annotations}

        updates: List[VectorDBUpdate] = []
        for doc in docs:
            ann = ann_by_entity.get(doc.entity_id)
            if not ann or not ann.refs:
                continue

            entity_type = doc.system_metadata.entity_type
            updates.append(VectorDBUpdate(
                id=f"{entity_type}_{doc.entity_id}",
                entity_schema=doc.system_metadata.entity_schema,
                fields={"airweave_system_metadata_annotations": [ref.prefixed for ref in ann.refs]},
            ))

        return updates
