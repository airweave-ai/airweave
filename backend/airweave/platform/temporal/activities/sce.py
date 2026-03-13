"""Temporal activity for Structural Context Extraction (SCE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import UUID

from temporalio import activity

from airweave.domains.sce.protocols import StructuralContextExtractorServiceProtocol
from airweave.domains.sce.types import EntityAnnotations, EntityExtractionInput
from airweave.platform.destinations._base import VectorDBUpdate
from airweave.schemas.search_result import AirweaveSearchResult

QUERY_BATCH_SIZE = 10000


@dataclass
class ExtractStructuralContextActivity:
    """Extract structural context (refs) from synced entities.

    Dependencies:
        sce_service: The SCE orchestration service (injected from container)
    """

    sce_service: StructuralContextExtractorServiceProtocol

    @activity.defn(name="extract_structural_context")
    async def run(self, collection_id: str, sync_id: str) -> Dict[str, Any]:
        """Fetch entities, extract structural refs, and write annotations back.

        Args:
            collection_id: The collection to extract from.
            sync_id: The sync job that produced the entities.
        """
        from airweave.core.logging import LoggerConfigurator
        from airweave.platform.destinations.vespa.destination import VespaDestination

        logger = LoggerConfigurator.configure_logger(
            "airweave.temporal.extract_structural_context",
            dimensions={
                "collection_id": collection_id,
                "sync_id": sync_id,
            },
        )

        cid = UUID(collection_id)
        sid = UUID(sync_id)

        summary: Dict[str, Any] = {
            "entities_annotated": 0,
            "errors": [],
        }

        try:
            vespa = await VespaDestination.create(
                collection_id=cid,
                logger=logger,
            )
        except Exception as e:
            error_msg = f"[SCE] Failed to create Vespa destination: {e}"
            logger.error(error_msg)
            summary["errors"].append(error_msg)
            return summary

        logger.info(f"[SCE] Starting extraction for collection={collection_id}, sync={sync_id}")

        offset = 0
        while True:
            logger.debug(f"[SCE] Querying batch limit={QUERY_BATCH_SIZE}, offset={offset}")
            docs = await vespa.query_documents(
                cid, sid, limit=QUERY_BATCH_SIZE, offset=offset
            )
            if not docs:
                break

            annotations = await self._extract_batch(docs)
            updates = self._build_updates(docs, annotations)
            await vespa.bulk_update(updates)
            summary["entities_annotated"] += len(updates)

            logger.info(f"[SCE] Batch done: docs={len(docs)} updated={len(updates)}")

            if len(docs) < QUERY_BATCH_SIZE:
                break
            offset += QUERY_BATCH_SIZE

        logger.info(
            f"Structural Context Extraction complete: {summary['entities_annotated']} annotated, "
            f"{len(summary['errors'])} error(s)"
        )

        return summary

    async def _extract_batch(
        self, documents: List[AirweaveSearchResult]
    ) -> List[EntityAnnotations]:
        """Run SCE on a batch of documents."""
        entity_inputs = [
            EntityExtractionInput(
                entity_id=doc.entity_id,
                text=doc.textual_representation,
                entity_type=doc.system_metadata.entity_type,
            )
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
