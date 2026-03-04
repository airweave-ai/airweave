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

from airweave.platform.entities._base import BaseEntity, CodeFileEntity
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.pipeline.text_builder import text_builder
from airweave.platform.sync.processors.protocol import ContentProcessor
from airweave.platform.sync.processors.utils import filter_empty_representations

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


class ChunkEmbedProcessor(ContentProcessor):
    """Unified processor that chunks text and computes embeddings.

    Pipeline:
    1. Build textual representation (text extraction from files/web)
    2. Chunk text (semantic for text, AST for code)
    3. Compute embeddings:
       - Dense embeddings (3072-dim for neural/semantic search)
       - Sparse embeddings (FastEmbed Qdrant/bm25 for keyword search scoring)

    Output:
        Chunk entities with:
        - entity_id: "{original_id}__chunk_{idx}"
        - textual_representation: chunk text
        - airweave_system_metadata.dense_embedding: 3072-dim vector
        - airweave_system_metadata.sparse_embedding: FastEmbed BM25 sparse vector
        - airweave_system_metadata.original_entity_id: original entity_id
        - airweave_system_metadata.chunk_index: chunk position
    """

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
        processed = await text_builder.build_for_batch(entities, sync_context, runtime)

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

        # Step 5: Embed chunks
        await self._embed_entities(chunk_entities, runtime)

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
        runtime: "SyncRuntime",
    ) -> None:
        """Compute dense and sparse embeddings for all destinations.

        Both Qdrant and Vespa use:
        - Dense embeddings (provider-specific dim) for neural/semantic search
        - Sparse embeddings (FastEmbed Qdrant/bm25) for keyword search scoring

        This ensures consistent keyword search behavior across both vector databases,
        with benefits of pre-trained vocabulary/IDF, stopword removal, and learned term weights.
        """
        if not chunk_entities:
            return

        expected_dims = runtime.dense_embedder.dimensions

        # Dense embeddings (provider-specific dimensions for neural search)
        dense_texts = [e.textual_representation for e in chunk_entities]
        dense_results = await runtime.dense_embedder.embed_many(dense_texts)
        dense_embeddings = [r.vector for r in dense_results]
        if (
            dense_embeddings
            and dense_embeddings[0] is not None
            and len(dense_embeddings[0]) != expected_dims
        ):
            raise SyncFailureError(
                "[ChunkEmbedProcessor] Dense embedding dimensions mismatch: "
                f"got {len(dense_embeddings[0])}, "
                f"expected {expected_dims}."
            )

        # Sparse embeddings (FastEmbed Qdrant/bm25 for keyword search scoring)
        # Uses full entity JSON (minus system metadata) to capture all searchable content
        sparse_texts = [
            json.dumps(
                e.model_dump(mode="json", exclude={"airweave_system_metadata"}),
                sort_keys=True,
            )
            for e in chunk_entities
        ]
        sparse_embeddings = await runtime.sparse_embedder.embed_many(sparse_texts)

        # Assign embeddings to entities
        for i, entity in enumerate(chunk_entities):
            entity.airweave_system_metadata.dense_embedding = dense_embeddings[i]
            entity.airweave_system_metadata.sparse_embedding = sparse_embeddings[i]

        # Validate
        for entity in chunk_entities:
            if entity.airweave_system_metadata.dense_embedding is None:
                raise SyncFailureError(f"Entity {entity.entity_id} has no dense embedding")
            if entity.airweave_system_metadata.sparse_embedding is None:
                raise SyncFailureError(f"Entity {entity.entity_id} has no sparse embedding")
