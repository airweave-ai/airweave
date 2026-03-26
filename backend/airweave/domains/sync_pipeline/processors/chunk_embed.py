"""Unified chunk and embed processor for vector databases.

Used by: Qdrant, Vespa, Pinecone, and similar vector DBs.

Both destinations use chunk-as-document model where each chunk becomes
a separate document with its own embedding. Both Qdrant and Vespa use:
- Dense embeddings (3072-dim) for neural/semantic search
- Sparse embeddings (FastEmbed Qdrant/bm25) for keyword search scoring

This ensures consistent keyword search behavior across both vector databases,
with benefits of pre-trained vocabulary/IDF, stopword removal, and learned term weights.
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from airweave.domains.converters.protocols import ConverterRegistryProtocol
from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError, SyncFailureError
from airweave.domains.sync_pipeline.pipeline.text_builder import TextualRepresentationBuilder
from airweave.domains.sync_pipeline.processors.utils import filter_empty_representations
from airweave.platform.entities._base import BaseEntity, CodeFileEntity

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.contexts import SyncContext
    from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime


class ChunkEmbedProcessor:
    """Unified processor that chunks text and computes embeddings."""

    def __init__(
        self,
        converter_registry: ConverterRegistryProtocol,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
    ) -> None:
        """Initialize with converter registry and embedding providers."""
        self._text_builder = TextualRepresentationBuilder(converter_registry)
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Process entities through full chunk+embed pipeline."""
        if not entities:
            return []

        # Step 1: Build textual representations
        processed = await self._text_builder.build_for_batch(entities, sync_context, runtime)

        # Step 2: Filter empty representations
        processed = await filter_empty_representations(
            processed, sync_context, runtime, "ChunkEmbed"
        )
        if not processed:
            sync_context.logger.debug("[ChunkEmbedProcessor] No entities after text building")
            return []

        # Step 3: Chunk entities
        chunk_entities = await self._chunk_entities(processed, sync_context, runtime)

        # Step 4: Release parent text (memory optimization)
        for entity in processed:
            entity.textual_representation = None

        # Step 5: Embed chunks (may remove entities that fail embedding)
        chunk_entities = await self._embed_entities(chunk_entities, sync_context)

        sync_context.logger.debug(
            f"[ChunkEmbedProcessor] {len(entities)} entities -> {len(chunk_entities)} chunks"
        )

        return chunk_entities

    # -------------------------------------------------------------------------
    # Chunking
    # -------------------------------------------------------------------------

    async def _chunk_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Route entities to appropriate chunker."""
        code_entities = [e for e in entities if isinstance(e, CodeFileEntity)]
        textual_entities = [e for e in entities if not isinstance(e, CodeFileEntity)]

        all_chunks: List[BaseEntity] = []

        if code_entities:
            chunks = await self._chunk_code_entities(code_entities, sync_context, runtime)
            all_chunks.extend(chunks)

        if textual_entities:
            chunks = await self._chunk_textual_entities(textual_entities, sync_context)
            all_chunks.extend(chunks)

        return all_chunks

    async def _chunk_code_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Chunk code with AST-aware CodeChunker."""
        from airweave.platform.chunkers.code import CodeChunker

        # Filter unsupported languages
        supported, unsupported = await self._filter_unsupported_languages(entities)
        if unsupported:
            await runtime.entity_tracker.record_skipped(len(unsupported))

        if not supported:
            return []

        chunker = CodeChunker()
        texts = [e.textual_representation for e in supported]

        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except Exception as e:
            raise SyncFailureError(f"[ChunkEmbedProcessor] CodeChunker failed: {e}")

        return self._multiply_entities(supported, chunk_lists, sync_context)

    async def _chunk_textual_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Chunk text with SemanticChunker."""
        from airweave.platform.chunkers.semantic import SemanticChunker

        chunker = SemanticChunker()
        texts = [e.textual_representation for e in entities]

        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except Exception as e:
            raise SyncFailureError(f"[ChunkEmbedProcessor] SemanticChunker failed: {e}")

        return self._multiply_entities(entities, chunk_lists, sync_context)

    async def _filter_unsupported_languages(
        self,
        entities: List[BaseEntity],
    ) -> Tuple[List[BaseEntity], List[BaseEntity]]:
        """Filter code entities by tree-sitter support."""
        try:
            from magika import Magika
            from tree_sitter_language_pack import get_parser
        except ImportError:
            return entities, []

        magika = Magika()
        supported: List[BaseEntity] = []
        unsupported: List[BaseEntity] = []

        for entity in entities:
            try:
                text_bytes = entity.textual_representation.encode("utf-8")
                result = magika.identify_bytes(text_bytes)
                lang = result.output.label.lower()
                get_parser(lang)
                supported.append(entity)
            except (LookupError, Exception):
                unsupported.append(entity)

        return supported, unsupported

    def _multiply_entities(
        self,
        entities: List[BaseEntity],
        chunk_lists: List[List[Dict[str, Any]]],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Create chunk entities from chunker output."""
        chunk_entities: List[BaseEntity] = []

        for entity, chunks in zip(entities, chunk_lists, strict=True):
            if not chunks:
                continue

            original_id = entity.entity_id

            for idx, chunk in enumerate(chunks):
                chunk_text = chunk.get("text", "")
                if not chunk_text or not chunk_text.strip():
                    continue

                chunk_entity = entity.model_copy(deep=True)
                chunk_entity.textual_representation = chunk_text
                chunk_entity.entity_id = f"{original_id}__chunk_{idx}"
                chunk_entity.airweave_system_metadata.chunk_index = idx
                chunk_entity.airweave_system_metadata.original_entity_id = original_id

                chunk_entities.append(chunk_entity)

        return chunk_entities

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    async def _embed_entities(
        self,
        chunk_entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Compute dense and sparse embeddings for all destinations.

        Both Qdrant and Vespa use:
        - Dense embeddings (provider-specific dim) for neural/semantic search
        - Sparse embeddings (FastEmbed Qdrant/bm25) for keyword search scoring

        If a batch embedding fails with a non-retryable provider error (e.g. OpenAI 400),
        falls back to embedding entities one-by-one and removes entities that cannot be
        embedded. This prevents a single bad entity from crashing the entire sync.

        Returns:
            The list of chunk entities that were successfully embedded (may be smaller
            than the input if some entities were skipped).
        """
        if not chunk_entities:
            return chunk_entities

        # Dense embeddings with fallback (may remove entities that fail)
        dense_results, chunk_entities = await self._dense_embed_with_fallback(
            chunk_entities, sync_context
        )
        if not chunk_entities:
            return []

        self._validate_dense_dimensions(dense_results)

        # Sparse embeddings (FastEmbed Qdrant/bm25 for keyword search scoring)
        sparse_texts = [
            json.dumps(
                e.model_dump(mode="json", exclude={"airweave_system_metadata"}),
                sort_keys=True,
            )
            for e in chunk_entities
        ]
        sparse_embeddings = await self._sparse_embedder.embed_many(sparse_texts)

        # Assign and validate embeddings
        for i, entity in enumerate(chunk_entities):
            entity.airweave_system_metadata.dense_embedding = dense_results[i].vector
            entity.airweave_system_metadata.sparse_embedding = sparse_embeddings[i]

        for entity in chunk_entities:
            if entity.airweave_system_metadata.dense_embedding is None:
                raise SyncFailureError(f"Entity {entity.entity_id} has no dense embedding")
            if entity.airweave_system_metadata.sparse_embedding is None:
                raise SyncFailureError(f"Entity {entity.entity_id} has no sparse embedding")

        return chunk_entities

    def _validate_dense_dimensions(self, dense_results: List[Any]) -> None:
        """Raise if dense embedding dimensions don't match the expected size."""
        if not dense_results:
            return
        expected = self._dense_embedder.dimensions
        actual_vec = dense_results[0].vector
        if actual_vec is not None and len(actual_vec) != expected:
            raise SyncFailureError(
                f"[ChunkEmbedProcessor] Dense embedding dimensions mismatch: "
                f"got {len(actual_vec)}, expected {expected}."
            )

    async def _dense_embed_with_fallback(
        self,
        chunk_entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> Tuple[List[Any], List[BaseEntity]]:
        """Run dense embedding with fallback to individual embedding on failure.

        Returns:
            Tuple of (dense embedding results, surviving entities). The entity list may be
            smaller than the input if some entities were skipped during fallback.
        """
        dense_texts: list[str] = []
        for e in chunk_entities:
            if e.textual_representation is None:
                raise EntityProcessingError(
                    f"[ChunkEmbedProcessor] ChunkEntity {e.entity_id} has no textual_representation"
                )
            dense_texts.append(e.textual_representation)

        entity_ids = [e.entity_id for e in chunk_entities]
        sync_context.logger.info(
            "[ChunkEmbedProcessor] Embedding %d chunk entities. Entity IDs: %s",
            len(chunk_entities),
            entity_ids,
        )

        try:
            results = await self._dense_embedder.embed_many(dense_texts)
            return results, chunk_entities
        except EmbedderProviderError as e:
            if e.retryable:
                raise
            sync_context.logger.warning(
                "[ChunkEmbedProcessor] Batch dense embedding failed (non-retryable), "
                "falling back to individual embedding for %d entities: %s",
                len(chunk_entities),
                e.message,
            )
            return await self._embed_individually(chunk_entities, sync_context)
        except Exception:
            sync_context.logger.error(
                "[ChunkEmbedProcessor] Dense embedding failed for entity IDs: %s",
                entity_ids,
            )
            raise

    async def _embed_individually(
        self,
        chunk_entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> Tuple[List[Any], List[BaseEntity]]:
        """Embed entities one-by-one, skipping any that fail.

        Returns:
            Tuple of (successful dense results, corresponding entities with failures removed).
        """
        successful_results: List[Any] = []
        successful_entities: List[BaseEntity] = []

        for entity in chunk_entities:
            try:
                results = await self._dense_embedder.embed_many(
                    [entity.textual_representation]  # type: ignore[list-item]
                )
                successful_results.append(results[0])
                successful_entities.append(entity)
            except Exception as exc:
                sync_context.logger.warning(
                    "[ChunkEmbedProcessor] Skipping entity %s — dense embedding failed: %s",
                    entity.entity_id,
                    str(exc)[:200],
                )

        skipped = len(chunk_entities) - len(successful_entities)
        if skipped:
            sync_context.logger.warning(
                "[ChunkEmbedProcessor] Skipped %d/%d entities due to embedding failures",
                skipped,
                len(chunk_entities),
            )

        return successful_results, successful_entities
