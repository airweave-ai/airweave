"""Unified chunk and embed processor for vector databases.

Used by: Qdrant, Vespa, Pinecone, and similar vector DBs.

Both destinations use chunk-as-document model where each chunk becomes
a separate document with its own embedding. Both Qdrant and Vespa use:
- Dense embeddings (3072-dim) for neural/semantic search
- Sparse embeddings (FastEmbed Qdrant/bm25) for keyword search scoring

This ensures consistent keyword search behavior across both vector databases,
with benefits of pre-trained vocabulary/IDF, stopword removal, and learned term weights.

When the dense embedder supports multimodal embedding (via
MultimodalDenseEmbedderProtocol), eligible FileEntity objects (PDF <= 6 pages,
PNG, JPEG, audio, video) are embedded natively — the provider API receives the
raw file bytes instead of extracted text.  Text extraction still runs for BM25
sparse scoring and answer generation.
"""

import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from airweave.domains.embedders.exceptions import EmbedderInputError, EmbedderProviderError
from airweave.domains.embedders.protocols import (
    EmbeddingPurpose,
    MultimodalDenseEmbedderProtocol,
)
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.pipeline.text_builder import text_builder
from airweave.platform.sync.processors.utils import filter_empty_representations

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime

logger = logging.getLogger(__name__)


class ChunkEmbedProcessor:
    """Unified processor that chunks text and computes embeddings.

    Pipeline:
    1. Build textual representation (text extraction from files/web)
    2. Chunk text (semantic for text, AST for code)
    3. Compute embeddings:
       - Dense embeddings (provider-specific dim for neural/semantic search)
       - Sparse embeddings (FastEmbed Qdrant/bm25 for keyword search scoring)

    When the dense embedder implements MultimodalDenseEmbedderProtocol,
    eligible file entities are routed to a native multimodal pipeline that
    embeds the raw file directly (1 chunk per entity, no text splitting).

    Output:
        Chunk entities with:
        - entity_id: "{original_id}__chunk_{idx}"
        - textual_representation: chunk text
        - airweave_system_metadata.dense_embedding: provider-dim vector
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

        # Partition: entities eligible for native multimodal vs text pipeline
        native_entities, text_entities = self._partition_by_embedding_mode(
            entities, runtime
        )

        all_chunks: List[BaseEntity] = []

        # --- Native multimodal pipeline ---
        if native_entities:
            native_chunks = await self._native_multimodal_pipeline(
                native_entities, sync_context, runtime
            )
            all_chunks.extend(native_chunks)

        # --- Text pipeline (existing logic) ---
        if text_entities:
            text_chunks = await self._text_pipeline(text_entities, sync_context, runtime)
            all_chunks.extend(text_chunks)

        sync_context.logger.debug(
            f"[ChunkEmbedProcessor] {len(entities)} entities -> {len(all_chunks)} chunks "
            f"(native={len(native_entities)}, text={len(text_entities)})"
        )

        return all_chunks

    # -------------------------------------------------------------------------
    # Partitioning
    # -------------------------------------------------------------------------

    def _partition_by_embedding_mode(
        self,
        entities: List[BaseEntity],
        runtime: "SyncRuntime",
    ) -> Tuple[List[BaseEntity], List[BaseEntity]]:
        """Split entities into native-multimodal and text-pipeline lists.

        An entity is eligible for native multimodal embedding when:
        1. The dense embedder implements MultimodalDenseEmbedderProtocol
        2. The entity is a FileEntity
        3. The entity has a supported mime_type
        4. The entity has a local_path on disk

        Everything else goes to the text pipeline.
        """
        embedder = runtime.dense_embedder

        if not isinstance(embedder, MultimodalDenseEmbedderProtocol):
            return [], list(entities)

        if not embedder.supports_multimodal:
            return [], list(entities)

        supported_mimes = embedder.supported_mime_types

        # Check if media sync is enabled — if not, exclude audio/video MIMEs
        # from native embedding regardless of source. This is the end-to-end
        # gate: even if a source emits audio/video entities, they won't be
        # routed to the native multimodal pipeline without the flag.
        try:
            from airweave.core.config import settings

            media_enabled = settings.ENABLE_MEDIA_SYNC
        except Exception:
            media_enabled = False

        native: List[BaseEntity] = []
        text: List[BaseEntity] = []

        for entity in entities:
            if not (
                isinstance(entity, FileEntity)
                and entity.mime_type
                and entity.mime_type in supported_mimes
                and entity.local_path
            ):
                text.append(entity)
                continue

            # Gate audio/video behind ENABLE_MEDIA_SYNC at the pipeline level
            if entity.mime_type in self._MEDIA_MIME_TYPES and not media_enabled:
                text.append(entity)
                continue

            native.append(entity)

        return native, text

    # -------------------------------------------------------------------------
    # Native multimodal pipeline
    # -------------------------------------------------------------------------

    _MEDIA_MIME_TYPES: set[str] = {"audio/mpeg", "audio/wav", "video/mp4"}


    async def _native_multimodal_pipeline(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Embed file entities natively.

        For images/PDFs: 1 chunk per entity (no text splitting).
        For audio/video: MediaChunker splits into segments, N chunks per entity.

        Steps:
        1. Run text extraction for textual_representation (BM25, answer gen)
        2. For each entity: embed file directly or chunk media first
        3. Compute sparse embedding from textual_representation
        4. Falls back to text pipeline on EmbedderInputError

        Falls back to the text pipeline for entities where embed_file() fails.
        """
        # Step 1: Build textual representations (reuses existing text pipeline)
        processed = await text_builder.build_for_batch(entities, sync_context, runtime)

        # Filter entities that failed text building
        processed = await filter_empty_representations(
            processed, sync_context, runtime, "ChunkEmbed-Multimodal"
        )
        if not processed:
            return []

        embedder = runtime.dense_embedder
        expected_dims = embedder.dimensions

        chunk_entities: List[BaseEntity] = []
        fallback_entities: List[BaseEntity] = []

        for entity in processed:
            file_entity: FileEntity = entity  # type: ignore[assignment]
            mime = file_entity.mime_type

            try:
                if mime in self._MEDIA_MIME_TYPES:
                    # Audio/video: chunk into segments, embed each
                    media_chunks = await self._embed_media_entity(
                        file_entity, embedder, expected_dims
                    )
                    chunk_entities.extend(media_chunks)
                else:
                    # Image/PDF: single embed
                    dense_result = await embedder.embed_file(  # type: ignore[union-attr]
                        file_entity.local_path,
                        file_entity.mime_type,
                        purpose=EmbeddingPurpose.DOCUMENT,
                    )

                    if len(dense_result.vector) != expected_dims:
                        raise SyncFailureError(
                            f"[ChunkEmbed-Multimodal] Dense embedding dimensions mismatch: "
                            f"got {len(dense_result.vector)}, expected {expected_dims}"
                        )

                    chunk = entity.model_copy(deep=True)
                    original_id = entity.entity_id
                    chunk.entity_id = f"{original_id}__chunk_0"
                    chunk.airweave_system_metadata.chunk_index = 0
                    chunk.airweave_system_metadata.original_entity_id = original_id
                    chunk.airweave_system_metadata.dense_embedding = dense_result.vector
                    chunk_entities.append(chunk)

            except (EmbedderInputError, EmbedderProviderError) as e:
                # For oversized PDFs, try chunking into 6-page segments
                if mime == "application/pdf" and isinstance(e, EmbedderInputError):
                    try:
                        sync_context.logger.info(
                            f"[ChunkEmbed-Multimodal] PDF {file_entity.entity_id} "
                            f"too large for single embed ({e}). Splitting into "
                            f"6-page chunks."
                        )
                        pdf_chunks = await self._embed_oversized_pdf(
                            file_entity, embedder, expected_dims
                        )
                        chunk_entities.extend(pdf_chunks)
                        continue
                    except (EmbedderInputError, EmbedderProviderError):
                        pass  # All PDF chunks failed, fall through to text

                sync_context.logger.warning(
                    f"[ChunkEmbed-Multimodal] embed_file failed for "
                    f"{file_entity.entity_id}: {e}. Falling back to text pipeline."
                )
                fallback_entities.append(entity)

        # Compute sparse embeddings for successfully embedded chunks
        if chunk_entities:
            sparse_texts = [
                json.dumps(
                    e.model_dump(mode="json", exclude={"airweave_system_metadata"}),
                    sort_keys=True,
                )
                for e in chunk_entities
            ]
            sparse_results = await runtime.sparse_embedder.embed_many(sparse_texts)
            for i, chunk in enumerate(chunk_entities):
                chunk.airweave_system_metadata.sparse_embedding = sparse_results[i]

        # Process fallback entities through the text pipeline.
        # skip_text_building=True because text was already extracted in step 1 above.
        if fallback_entities:
            fallback_chunks = await self._text_pipeline(
                fallback_entities, sync_context, runtime,
                skip_text_building=True,
            )
            chunk_entities.extend(fallback_chunks)

        # Release parent text (memory optimization)
        for entity in processed:
            entity.textual_representation = None

        return chunk_entities

    async def _embed_media_entity(
        self,
        entity: "FileEntity",
        embedder: Any,
        expected_dims: int,
    ) -> List[BaseEntity]:
        """Chunk and embed a media (audio/video) entity.

        Uses MediaChunker to split the file into segments, then embeds
        each segment individually via embed_file(). Per-segment errors
        are logged and skipped (partial results returned). Temp dirs
        are cleaned up via the context manager.
        """
        from airweave.platform.chunkers.media import MediaChunker, MediaSegment

        async with MediaChunker() as chunker:
            mime = entity.mime_type
            original_id = entity.entity_id

            if mime in ("audio/mpeg", "audio/wav"):
                segments: list[MediaSegment] = await chunker.chunk_audio(entity.local_path)
            else:
                segments = await chunker.chunk_video(entity.local_path)

            chunks: List[BaseEntity] = []
            for idx, segment in enumerate(segments):
                try:
                    dense_result = await embedder.embed_file(
                        segment.file_path,
                        segment.mime_type,
                        purpose=EmbeddingPurpose.DOCUMENT,
                    )

                    if len(dense_result.vector) != expected_dims:
                        logger.warning(
                            f"[ChunkEmbed-Multimodal] Dimension mismatch on segment {idx} "
                            f"of {original_id}: got {len(dense_result.vector)}, "
                            f"expected {expected_dims}. Skipping segment."
                        )
                        continue

                    chunk = entity.model_copy(deep=True)
                    chunk.entity_id = f"{original_id}__chunk_{idx}"
                    chunk.airweave_system_metadata.chunk_index = idx
                    chunk.airweave_system_metadata.original_entity_id = original_id
                    chunk.airweave_system_metadata.dense_embedding = dense_result.vector

                    # Assign segment-specific textual_representation so each
                    # chunk gets its own sparse embedding and answer context,
                    # not the full parent transcript duplicated across all chunks.
                    parent_text = entity.textual_representation or ""
                    chunk.textual_representation = (
                        f"[Segment {idx}: {segment.start_seconds:.1f}s - "
                        f"{segment.end_seconds:.1f}s] {parent_text}"
                    )

                    chunks.append(chunk)

                except (EmbedderInputError, EmbedderProviderError) as e:
                    logger.warning(
                        f"[ChunkEmbed-Multimodal] Segment {idx} of {original_id} "
                        f"failed: {e}. Skipping segment."
                    )
                    continue

        if not chunks:
            raise EmbedderInputError(
                f"All segments failed for {entity.entity_id}"
            )

        return chunks

    async def _embed_oversized_pdf(
        self,
        entity: "FileEntity",
        embedder: Any,
        expected_dims: int,
    ) -> List[BaseEntity]:
        """Split an oversized PDF into page-limited chunks and embed.

        Uses PyMuPDF to split the PDF with configurable page count and overlap.

        Each page-chunk is embedded independently, producing N separate vectors
        in Vespa. This matches Airweave's text chunking model where each chunk
        is independently searchable. Gemini limits document parts to 1 per
        content entry, so API-native aggregation is not possible for PDFs.
        """
        import tempfile

        import fitz  # PyMuPDF

        from airweave.core.config import settings

        file_path = entity.local_path
        original_id = entity.entity_id
        max_pages = settings.MULTIMODAL_PDF_MAX_PAGES
        overlap_pages = settings.MULTIMODAL_PDF_OVERLAP_PAGES

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise EmbedderInputError(f"Failed to open PDF for chunking: {e}") from e

        total_pages = len(doc)
        temp_files: list[str] = []
        step = max(1, max_pages - overlap_pages)

        try:
            # Step 1: Split PDF into chunk files
            start_page = 0
            while start_page < total_pages:
                end_page = min(start_page + max_pages, total_pages)

                chunk_doc = fitz.open()
                chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)

                # Use NamedTemporaryFile to avoid TOCTOU race from mktemp
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".pdf", prefix="pdf_chunk_", delete=False
                )
                chunk_path = tmp.name
                tmp.close()
                chunk_doc.save(chunk_path)
                chunk_doc.close()
                temp_files.append(chunk_path)

                start_page += step

            doc.close()

            # Step 2: Embed each chunk independently.
            # Gemini limits document parts to 1 per content entry.
            chunks: List[BaseEntity] = []
            for idx, chunk_path in enumerate(temp_files):
                try:
                    dense_result = await embedder.embed_file(
                        chunk_path,
                        "application/pdf",
                        purpose=EmbeddingPurpose.DOCUMENT,
                    )

                    if len(dense_result.vector) != expected_dims:
                        logger.warning(
                            f"[ChunkEmbed-Multimodal] PDF chunk {idx} "
                            f"dimension mismatch. Skipping."
                        )
                        continue

                    chunk = entity.model_copy(deep=True)
                    chunk.entity_id = f"{original_id}__chunk_{idx}"
                    chunk.airweave_system_metadata.chunk_index = idx
                    chunk.airweave_system_metadata.original_entity_id = original_id
                    chunk.airweave_system_metadata.dense_embedding = dense_result.vector
                    chunks.append(chunk)

                except (EmbedderInputError, EmbedderProviderError) as e:
                    logger.warning(
                        f"[ChunkEmbed-Multimodal] PDF chunk {idx} "
                        f"failed: {e}. Skipping."
                    )

            if not chunks:
                raise EmbedderInputError(
                    f"All PDF chunks failed for {entity.entity_id}"
                )

            return chunks

        finally:
            for f in temp_files:
                try:
                    os.remove(f)
                except OSError:
                    pass

    # -------------------------------------------------------------------------
    # Text pipeline (existing logic, extracted)
    # -------------------------------------------------------------------------

    async def _text_pipeline(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
        *,
        skip_text_building: bool = False,
    ) -> List[BaseEntity]:
        """Process entities through the standard text chunk+embed pipeline.

        Args:
            skip_text_building: If True, skip text_builder (entities already
                have textual_representation from the multimodal pipeline).
        """
        # Step 1: Build textual representations (skip if already done)
        if skip_text_building:
            processed = entities
        else:
            processed = await text_builder.build_for_batch(entities, sync_context, runtime)

        # Step 2: Filter empty representations
        processed = await filter_empty_representations(
            processed, sync_context, runtime, "ChunkEmbed"
        )
        if not processed:
            return []

        # Step 3: Chunk entities
        chunk_entities = await self._chunk_entities(processed, sync_context, runtime)

        # Step 4: Release parent text (memory optimization)
        for entity in processed:
            entity.textual_representation = None

        # Step 5: Embed chunks
        await self._embed_entities(chunk_entities, sync_context, runtime)

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

        if runtime.dense_embedder is None:
            return

        expected_dims = runtime.dense_embedder.dimensions

        # Dense embeddings (provider-specific dimensions for neural search)
        dense_texts = [e.textual_representation or "" for e in chunk_entities]
        entity_ids = [e.entity_id for e in chunk_entities]
        sync_context.logger.info(
            "[ChunkEmbedProcessor] Embedding %d chunk entities. Entity IDs: %s",
            len(chunk_entities),
            entity_ids,
        )
        try:
            dense_results = await runtime.dense_embedder.embed_many(
                dense_texts, purpose=EmbeddingPurpose.DOCUMENT
            )
        except Exception:
            sync_context.logger.error(
                "[ChunkEmbedProcessor] Dense embedding failed for entity IDs: %s",
                entity_ids,
            )
            raise
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
