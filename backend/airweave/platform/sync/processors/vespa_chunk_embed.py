"""Vespa chunk and embed processor - unified chunk-as-document architecture.

Like QdrantChunkEmbedProcessor, this creates separate chunk entities (1:N expansion).
Each chunk becomes its own document in Vespa with:
- entity_id: "{original_id}__chunk_{idx}"
- original_entity_id: original entity_id
- vectors: [large_768_float_embedding]
- packed_vectors: binary-packed int8 for ANN (96 int8)

This unifies the architecture between Qdrant and Vespa for fair comparison.
"""

import time
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import numpy as np

from airweave.platform.entities._base import BaseEntity, CodeFileEntity
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
    """Processor for Vespa using chunk-as-document model (same as Qdrant).

    Pipeline:
    1. Build textual representation (text extraction from files/web)
    2. Chunk text (semantic for text, AST for code)
    3. Compute 768-dim embeddings via OpenAI (single API call per chunk batch)
    4. Binary-pack embeddings for ANN index (768 float → 96 int8)
    5. Create chunk entities (1:N expansion)

    Output:
        Chunk entities with:
        - entity_id: "{original_id}__chunk_{idx}"
        - textual_representation: chunk text
        - airweave_system_metadata.vectors: [large_768_float_embedding]
        - airweave_system_metadata.packed_vectors: binary-packed int8 (96 int8)
        - airweave_system_metadata.original_entity_id: original entity_id
        - airweave_system_metadata.chunk_index: chunk position
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
            Chunk entities (N per input entity)
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

        # Step 3: Chunk entities and create chunk entities (1:N expansion)
        step_start = time.perf_counter()
        chunk_entities = await self._chunk_entities(processed, sync_context)
        chunk_ms = (time.perf_counter() - step_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Chunking: {chunk_ms:.1f}ms → "
            f"{len(chunk_entities)} chunks from {len(processed)} entities"
        )

        # Step 4: Release parent text (memory optimization)
        for entity in processed:
            entity.textual_representation = None

        if not chunk_entities:
            sync_context.logger.debug("[VespaChunkEmbedProcessor] No chunks generated")
            return []

        # Step 5: Embed all chunks (768-dim)
        step_start = time.perf_counter()
        await self._embed_entities(chunk_entities, sync_context)
        embed_ms = (time.perf_counter() - step_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] Embedding: {embed_ms:.1f}ms "
            f"for {len(chunk_entities)} chunks"
        )

        total_ms = (time.perf_counter() - total_start) * 1000
        sync_context.logger.debug(
            f"[VespaChunkEmbedProcessor] TOTAL: {total_ms:.1f}ms | "
            f"{len(entities)} entities → {len(chunk_entities)} chunks | "
            f"text={text_build_ms:.0f}ms, chunk={chunk_ms:.0f}ms, embed={embed_ms:.0f}ms"
        )

        return chunk_entities

    # -------------------------------------------------------------------------
    # Chunking (same as QdrantChunkEmbedProcessor)
    # -------------------------------------------------------------------------

    async def _chunk_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Route entities to appropriate chunker and create chunk entities."""
        code_entities = [e for e in entities if isinstance(e, CodeFileEntity)]
        textual_entities = [e for e in entities if not isinstance(e, CodeFileEntity)]

        all_chunks: List[BaseEntity] = []

        if code_entities:
            chunks = await self._chunk_code_entities(code_entities, sync_context)
            all_chunks.extend(chunks)

        if textual_entities:
            chunks = await self._chunk_textual_entities(textual_entities, sync_context)
            all_chunks.extend(chunks)

        return all_chunks

    async def _chunk_code_entities(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Chunk code with AST-aware CodeChunker."""
        from airweave.platform.chunkers.code import CodeChunker

        # Filter unsupported languages
        supported, unsupported = await self._filter_unsupported_languages(entities)
        if unsupported:
            await sync_context.entity_tracker.record_skipped(len(unsupported))

        if not supported:
            return []

        chunker = CodeChunker()
        texts = [e.textual_representation for e in supported]

        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except Exception as e:
            raise SyncFailureError(f"[VespaChunkEmbedProcessor] CodeChunker failed: {e}")

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
            raise SyncFailureError(f"[VespaChunkEmbedProcessor] SemanticChunker failed: {e}")

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
        """Create chunk entities from chunker output (same as Qdrant).

        Preserves character positions (start_index, end_index) from chunker output
        for span-based evaluation. This allows checking if retrieved chunks overlap
        with labeled spans, independent of chunking strategy.
        """
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

                # Store character positions for span-based evaluation
                chunk_entity.airweave_system_metadata.chunk_start_char = chunk.get("start_index")
                chunk_entity.airweave_system_metadata.chunk_end_char = chunk.get("end_index")

                chunk_entities.append(chunk_entity)

        return chunk_entities

    # -------------------------------------------------------------------------
    # Embedding (Vespa-specific: large float + small binary-packed)
    # -------------------------------------------------------------------------

    async def _embed_entities(
        self,
        chunk_entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> None:
        """Compute large (768-dim float) and small (96-dim int8 packed) embeddings.

        Unlike Qdrant (dense + sparse), Vespa uses:
        - vectors[0]: 768-dim float embedding for ranking (cosine similarity)
        - packed_vectors: 96 int8 binary-packed for ANN index (hamming distance)
        """
        if not chunk_entities:
            return

        from airweave.platform.embedders import DenseEmbedder

        # Embed all chunks at once (768-dim)
        texts = [e.textual_representation for e in chunk_entities]
        embedder = DenseEmbedder()  # Uses text-embedding-3-large
        large_embeddings = await embedder.embed_many(
            texts, sync_context, dimensions=LARGE_EMBEDDING_DIM
        )

        # Assign vectors and packed_vectors to entities
        for i, entity in enumerate(chunk_entities):
            large_emb = large_embeddings[i]
            small_emb = self._pack_bits(large_emb)

            # Store large embedding in vectors (for ranking)
            entity.airweave_system_metadata.vectors = [large_emb]
            # Store binary-packed embedding for ANN index
            entity.airweave_system_metadata.packed_vectors = small_emb

        # Validate
        for entity in chunk_entities:
            if not entity.airweave_system_metadata.vectors:
                raise SyncFailureError(f"Entity {entity.entity_id} has no vectors")
            if entity.airweave_system_metadata.packed_vectors is None:
                raise SyncFailureError(f"Entity {entity.entity_id} has no packed_vectors")

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
        packed = np.packbits(bits)

        # Convert to signed int8 (-128 to 127) for Vespa
        packed_int8 = packed.astype(np.int8)

        return packed_int8.tolist()
