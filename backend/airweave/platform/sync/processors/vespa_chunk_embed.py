"""Vespa chunk and embed processor for entity-as-document architecture.

Unlike QdrantChunkEmbedProcessor which creates separate chunk entities,
this processor keeps the original entity and stores chunks + embeddings as arrays
within entity.vespa_content.

Key differences from QdrantChunkEmbedProcessor:
- Output: N entities → N entities (1:1, not 1:N)
- entity_id: Unchanged (no __chunk_N suffix)
- Content location: entity.vespa_content (not airweave_system_metadata.vectors)
- Embedding: 768-dim for ranking + binary-packed 96 int8 for ANN
"""

import time
from typing import TYPE_CHECKING, Any, Dict, List

import numpy as np

from airweave.platform.entities._base import BaseEntity, CodeFileEntity, VespaContent
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.pipeline.text_builder import text_builder
from airweave.platform.sync.processors.protocol import ContentProcessor
from airweave.platform.sync.processors.utils import filter_empty_representations

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


# Constants for Vespa embedding dimensions
LARGE_EMBEDDING_DIM = 768  # Full precision for ranking (bfloat16 in Vespa)
SMALL_EMBEDDING_DIM = 96  # Binary-packed for ANN (768 bits → 96 bytes)


class VespaChunkEmbedProcessor(ContentProcessor):
    """Processor for Vespa's entity-as-document model.

    Pipeline:
    1. Build textual representation (text extraction from files/web)
    2. Chunk text (semantic for text, AST for code)
    3. Compute 768-dim embeddings via OpenAI (single API call per chunk batch)
    4. Binary-pack embeddings for ANN index (768 float → 96 int8)

    Output:
        Same entities with vespa_content populated:
        - chunks: List[str] - chunked text segments
        - chunk_large_embeddings: List[List[float]] - 768-dim for ranking
        - chunk_small_embeddings: List[List[int]] - binary-packed for ANN
    """

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Process entities through Vespa chunk+embed pipeline.

        Args:
            entities: Entities to process
            sync_context: Sync context with logger, collection info, etc.

        Returns:
            Same entities with vespa_content populated
        """
        if not entities:
            return []

        total_start = time.perf_counter()
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Starting processing of {len(entities)} entities"
        )

        # Step 1: Build textual representations
        step_start = time.perf_counter()
        processed = await text_builder.build_for_batch(entities, sync_context)
        text_build_ms = (time.perf_counter() - step_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Text building: {text_build_ms:.1f}ms "
            f"for {len(processed)} entities"
        )

        # Step 2: Filter empty representations
        processed = await filter_empty_representations(processed, sync_context, "VespaChunkEmbed")
        if not processed:
            sync_context.logger.debug("[VespaChunkEmbedProcessor] No entities after text building")
            return []

        # Step 3: Chunk entities (returns chunk lists per entity)
        step_start = time.perf_counter()
        chunk_lists = await self._chunk_entities(processed, sync_context)
        chunk_ms = (time.perf_counter() - step_start) * 1000
        total_chunks = sum(len(cl) for cl in chunk_lists)
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Chunking: {chunk_ms:.1f}ms → "
            f"{total_chunks} chunks from {len(processed)} entities"
        )

        # Step 4: Flatten chunks for batch embedding
        all_chunks, chunk_counts = self._flatten_chunks(chunk_lists)

        if not all_chunks:
            sync_context.logger.debug("[VespaChunkEmbedProcessor] No chunks generated")
            return []

        # Step 5: Embed all chunks in one batch (768-dim)
        step_start = time.perf_counter()
        large_embeddings = await self._embed_chunks(all_chunks, sync_context)
        embed_ms = (time.perf_counter() - step_start) * 1000
        ms_per_chunk = embed_ms / len(all_chunks)
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] OpenAI embedding: {embed_ms:.1f}ms "
            f"for {len(all_chunks)} chunks ({ms_per_chunk:.1f}ms/chunk)"
        )

        # Step 6: Binary pack embeddings for ANN (768 float → 96 int8)
        step_start = time.perf_counter()
        small_embeddings = [self._pack_bits(emb) for emb in large_embeddings]
        pack_ms = (time.perf_counter() - step_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Binary packing: {pack_ms:.1f}ms "
            f"for {len(large_embeddings)} embeddings"
        )

        # Step 7: Assign to entities (unflatten)
        step_start = time.perf_counter()
        self._assign_vespa_content(processed, chunk_lists, large_embeddings, small_embeddings)
        assign_ms = (time.perf_counter() - step_start) * 1000

        total_ms = (time.perf_counter() - total_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] TOTAL: {total_ms:.1f}ms | "
            f"{len(entities)} entities → {sum(chunk_counts)} chunks | "
            f"text={text_build_ms:.0f}ms, chunk={chunk_ms:.0f}ms, embed={embed_ms:.0f}ms, "
            f"pack={pack_ms:.0f}ms, assign={assign_ms:.0f}ms"
        )

        return processed

    # -------------------------------------------------------------------------
    # Chunking
    # -------------------------------------------------------------------------

    async def _chunk_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[List[Dict[str, Any]]]:
        """Chunk all entities, routing to appropriate chunker.

        Returns:
            List of chunk lists (one per entity), preserving order
        """
        # Separate code and text entities while preserving indices
        code_indices = [i for i, e in enumerate(entities) if isinstance(e, CodeFileEntity)]
        text_indices = [i for i, e in enumerate(entities) if not isinstance(e, CodeFileEntity)]

        code_entities = [entities[i] for i in code_indices]
        text_entities = [entities[i] for i in text_indices]

        # Initialize result list (will be filled at correct indices)
        chunk_lists: List[List[Dict[str, Any]]] = [[] for _ in entities]

        # Process code entities
        if code_entities:
            code_chunk_lists = await self._chunk_code_entities(code_entities, sync_context)
            for i, chunks in zip(code_indices, code_chunk_lists, strict=True):
                chunk_lists[i] = chunks

        # Process text entities
        if text_entities:
            text_chunk_lists = await self._chunk_text_entities(text_entities, sync_context)
            for i, chunks in zip(text_indices, text_chunk_lists, strict=True):
                chunk_lists[i] = chunks

        return chunk_lists

    async def _chunk_code_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[List[Dict[str, Any]]]:
        """Chunk code with AST-aware CodeChunker."""
        from airweave.platform.chunkers.code import CodeChunker

        # Filter unsupported languages
        supported, unsupported = await self._filter_unsupported_languages(entities)
        if unsupported:
            await sync_context.entity_tracker.record_skipped(len(unsupported))

        if not supported:
            return [[] for _ in entities]

        chunker = CodeChunker()
        texts = [e.textual_representation for e in supported]

        try:
            supported_chunk_lists = await chunker.chunk_batch(texts)
        except Exception as e:
            raise SyncFailureError(f"[VespaChunkEmbedProcessor] CodeChunker failed: {e}")

        # Map back to original entity order
        # Create lookup: entity -> chunk_list
        supported_map = {
            id(e): chunks for e, chunks in zip(supported, supported_chunk_lists, strict=True)
        }

        # Return chunk lists in original order (empty list for unsupported)
        return [supported_map.get(id(e), []) for e in entities]

    async def _chunk_text_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[List[Dict[str, Any]]]:
        """Chunk text with SemanticChunker."""
        from airweave.platform.chunkers.semantic import SemanticChunker

        chunker = SemanticChunker()
        texts = [e.textual_representation for e in entities]

        try:
            return await chunker.chunk_batch(texts)
        except Exception as e:
            raise SyncFailureError(f"[VespaChunkEmbedProcessor] SemanticChunker failed: {e}")

    async def _filter_unsupported_languages(
        self,
        entities: List[BaseEntity],
    ) -> tuple[List[BaseEntity], List[BaseEntity]]:
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

    def _flatten_chunks(
        self,
        chunk_lists: List[List[Dict[str, Any]]],
    ) -> tuple[List[str], List[int]]:
        """Flatten chunk lists for batch embedding.

        Returns:
            Tuple of (all_chunk_texts, chunk_counts_per_entity)
        """
        all_chunks: List[str] = []
        chunk_counts: List[int] = []

        for chunks in chunk_lists:
            chunk_texts = [c.get("text", "") for c in chunks if c.get("text", "").strip()]
            all_chunks.extend(chunk_texts)
            chunk_counts.append(len(chunk_texts))

        return all_chunks, chunk_counts

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    async def _embed_chunks(
        self,
        chunks: List[str],
        sync_context: "SyncContext",
    ) -> List[List[float]]:
        """Embed all chunks in one batch using 768-dim Matryoshka embeddings.

        Uses text-embedding-3-large model (3072 native dims) with Matryoshka truncation
        to get 768-dim embeddings. This provides a good balance between quality and
        storage cost for Vespa's two-phase ranking (ANN + re-ranking).

        Args:
            chunks: List of chunk texts
            sync_context: Sync context with logger

        Returns:
            List of 768-dim embeddings
        """
        from airweave.platform.embedders import DenseEmbedder

        # Use default model (text-embedding-3-large) and request 768-dim via Matryoshka
        # Note: Don't pass vector_size - that selects a model. Use dimensions param instead.
        embedder = DenseEmbedder()  # Uses text-embedding-3-large (3072 native dims)
        embeddings = await embedder.embed_many(chunks, sync_context, dimensions=LARGE_EMBEDDING_DIM)

        return embeddings

    def _pack_bits(self, embedding: List[float]) -> List[int]:
        """Binary pack a float embedding into int8 for Vespa's hamming distance.

        Mimics Vespa's pack_bits behavior:
        1. Threshold at 0: positive → 1, negative/zero → 0
        2. Pack 8 bits into 1 byte (int8)

        Args:
            embedding: 768-dim float embedding

        Returns:
            96 int8 values (768 bits packed into 96 bytes)
        """
        arr = np.array(embedding, dtype=np.float32)

        # Binary quantization: positive → 1, else → 0
        bits = (arr > 0).astype(np.uint8)

        # Pack 8 bits per byte (big-endian to match Vespa)
        # np.packbits packs bits into bytes
        packed = np.packbits(bits)

        # Convert to signed int8 (-128 to 127) for Vespa
        # Note: Vespa expects int8, packbits returns uint8
        packed_int8 = packed.astype(np.int8)

        return packed_int8.tolist()

    # -------------------------------------------------------------------------
    # Assignment
    # -------------------------------------------------------------------------

    def _assign_vespa_content(
        self,
        entities: List[BaseEntity],
        chunk_lists: List[List[Dict[str, Any]]],
        large_embeddings: List[List[float]],
        small_embeddings: List[List[int]],
    ) -> None:
        """Assign chunked content and embeddings to entities.

        Unflattens the embedding results back to per-entity arrays.

        Args:
            entities: Entities to update
            chunk_lists: Chunk dicts per entity (for text extraction)
            large_embeddings: Flat list of 768-dim embeddings
            small_embeddings: Flat list of 96 int8 embeddings
        """
        idx = 0
        for entity, chunks in zip(entities, chunk_lists, strict=True):
            # Filter empty chunks (same logic as _flatten_chunks)
            valid_chunks = [c for c in chunks if c.get("text", "").strip()]
            count = len(valid_chunks)

            if count == 0:
                # Entity has no valid chunks - set empty content
                entity.vespa_content = VespaContent(
                    chunks=[],
                    chunk_small_embeddings=[],
                    chunk_large_embeddings=[],
                )
                continue

            # Extract chunk texts
            chunk_texts = [c["text"] for c in valid_chunks]

            # Slice embeddings for this entity
            entity_large_embs = large_embeddings[idx : idx + count]
            entity_small_embs = small_embeddings[idx : idx + count]

            # Populate vespa_content
            entity.vespa_content = VespaContent(
                chunks=chunk_texts,
                chunk_small_embeddings=entity_small_embs,
                chunk_large_embeddings=entity_large_embs,
            )

            idx += count
