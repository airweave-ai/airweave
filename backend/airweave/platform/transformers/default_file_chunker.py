"""Default file transformer using Chonkie for improved semantic chunking."""

import asyncio
import os

import aiofiles
from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules, SemanticChunker

from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base_legacy import ChunkEntity, FileEntity
from airweave.platform.file_handling.conversion.factory import document_converter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.transformers.utils import (
    MARGIN_OF_ERROR,
    MAX_CHUNK_SIZE,
    METADATA_SIZE,
    count_tokens,
)

# Module-level shared chunker and cache
_shared_semantic_chunker = None
_semantic_chunker_cache = {}
_cache_lock = None

# Flag to control which chunking approach to use
USE_OPTIMIZED_CHUNKING = True  # Set to True to use faster token-based chunking

# Calculate safe chunk size accounting for metadata overhead
SAFE_CHUNK_SIZE = MAX_CHUNK_SIZE - METADATA_SIZE - MARGIN_OF_ERROR  # 7500 - 1200 - 250 = 6050


def get_recursive_chunker():
    """Create a RecursiveChunker for markdown with custom rules."""
    # Use a very large value to focus on structure rather than size
    structure_based_size = 1000000  # Effectively unlimited

    # Custom markdown chunking rules
    custom_rules = RecursiveRules(
        [
            RecursiveLevel(
                delimiters=["\n# "],
                include_delim="next",  # Include the delimiter in the next chunk
            ),
            RecursiveLevel(delimiters=["\n## "], include_delim="next"),
            RecursiveLevel(delimiters=["\n### "], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n- ", "\n* ", "\n1. "], include_delim="next"),
            RecursiveLevel(delimiters=["```"], include_delim="both"),
            RecursiveLevel(delimiters=[". ", "? ", "! "], include_delim="prev"),
        ]
    )

    return RecursiveChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=structure_based_size,
        rules=custom_rules,
        min_characters_per_chunk=100,
    )


async def get_optimized_semantic_chunker(
    max_chunk_size: int = SAFE_CHUNK_SIZE, entity_context: str = "", logger: ContextualLogger = None
):
    """Get an optimized semantic chunker with caching and connection pooling.

    This creates chunkers in a pool to avoid repeated initialization overhead.
    """
    global _semantic_chunker_cache, _cache_lock

    # Initialize cache lock if needed
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()

    cache_key = f"semantic_{max_chunk_size}"

    async with _cache_lock:
        if cache_key not in _semantic_chunker_cache:
            logger.debug(f"🧠 CHUNKER_CACHE_MISS [{entity_context}] Creating new semantic chunker")

            def _create_semantic_chunker():
                return SemanticChunker(
                    embedding_model="text-embedding-ada-002",
                    chunk_size=max_chunk_size,
                    threshold=0.5,
                    mode="window",
                    min_sentences=1,
                    similarity_window=2,
                )

            # Create in thread pool
            chunker = await run_in_thread_pool(_create_semantic_chunker)
            _semantic_chunker_cache[cache_key] = chunker
            logger.debug(f"🧠 CHUNKER_CACHE_ADD [{entity_context}] Added chunker to cache")
        else:
            logger.debug(f"🧠 CHUNKER_CACHE_HIT [{entity_context}] Using cached semantic chunker")

    return _semantic_chunker_cache[cache_key]


async def _process_file_content(
    file: FileEntity, entity_context: str, logger: ContextualLogger
) -> str:
    """Process file content and convert to text if needed."""
    if not file.airweave_system_metadata.local_path:
        logger.warning(f"📂 CHUNKER_NO_PATH [{entity_context}] File has no local path")
        return ""

    _, extension = os.path.splitext(file.airweave_system_metadata.local_path)
    extension = extension.lower()

    if extension == ".md":
        logger.debug(f"📑 CHUNKER_READ_MD [{entity_context}] Reading markdown file directly")
        async with aiofiles.open(
            file.airweave_system_metadata.local_path, "r", encoding="utf-8"
        ) as f:
            content = await f.read()
        logger.debug(f"📖 CHUNKER_READ_DONE [{entity_context}] Read {len(content)} characters")
        return content
    else:
        logger.debug(f"🔄 CHUNKER_CONVERT [{entity_context}] Converting file to markdown")
        result = await document_converter.convert(file.airweave_system_metadata.local_path)
        if not result or not result.text_content:
            logger.warning(f"🚫 CHUNKER_CONVERT_EMPTY [{entity_context}] No content extracted")
            return ""
        logger.debug(
            f"✅ CHUNKER_CONVERT_DONE [{entity_context}] "
            f"Converted to {len(result.text_content)} characters"
        )
        return result.text_content


async def _chunk_text_content(
    text_content: str, entity_context: str, logger: ContextualLogger
) -> list[str]:
    """Chunk text content using recursive and semantic chunkers with optimization."""
    # Use optimized chunking if flag is set
    if USE_OPTIMIZED_CHUNKING:
        logger.debug(
            f"🚀 CHUNKER_OPTIMIZED_MODE [{entity_context}] Using optimized token-based chunking"
        )
        from airweave.platform.transformers.optimized_file_chunker import _chunk_text_optimized

        return await _chunk_text_optimized(text_content, entity_context, logger)

    # Perform recursive chunking
    initial_chunks = await _perform_recursive_chunking(text_content, entity_context, logger)

    # Separate chunks by size
    small_chunks, large_chunks_data = _separate_chunks_by_size(initial_chunks)

    if not large_chunks_data:
        return small_chunks

    # Process large chunks with semantic chunking
    large_chunk_results = await _process_large_chunks_semantically(
        large_chunks_data, entity_context, logger
    )

    # Reconstruct final chunk list
    return _reconstruct_chunk_list(initial_chunks, small_chunks, large_chunk_results)


async def _perform_recursive_chunking(
    text_content: str, entity_context: str, logger: ContextualLogger
) -> list:
    """Perform initial recursive chunking."""
    logger.debug(f"🔧 CHUNKER_RECURSIVE_START [{entity_context}] Starting recursive chunking")

    recursive_chunker = get_recursive_chunker()
    initial_chunks = await run_in_thread_pool(recursive_chunker.chunk, text_content)

    logger.debug(
        f"📝 CHUNKER_RECURSIVE_DONE [{entity_context}] Created {len(initial_chunks)} initial chunks"
    )
    return initial_chunks


def _separate_chunks_by_size(initial_chunks: list) -> tuple[list[str], list[tuple]]:
    """Separate chunks into small and large based on token count."""
    small_chunks = []
    large_chunks_data = []

    for i, chunk in enumerate(initial_chunks):
        if chunk.token_count <= SAFE_CHUNK_SIZE:
            small_chunks.append(chunk.text)
        else:
            large_chunks_data.append((i, chunk))

    return small_chunks, large_chunks_data


async def _process_large_chunks_semantically(
    large_chunks_data: list[tuple], entity_context: str, logger: ContextualLogger
) -> dict:
    """Process large chunks using semantic chunking."""
    large_chunk_count = len(large_chunks_data)

    logger.debug(
        f"🧠 CHUNKER_LARGE_CHUNKS [{entity_context}] "
        f"Found {large_chunk_count} large chunks that need semantic chunking"
    )

    # Pre-load semantic chunker
    semantic_chunker = await get_optimized_semantic_chunker(SAFE_CHUNK_SIZE, entity_context, logger)

    # Set up parallel processing
    max_concurrent = min(5, large_chunk_count)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(chunk_data):
        async with semaphore:
            return await _process_single_large_chunk(
                chunk_data, semantic_chunker, entity_context, logger
            )

    # Process all chunks in parallel
    logger.debug(
        f"🔄 CHUNKER_PARALLEL_START [{entity_context}] "
        f"Processing {large_chunk_count} large chunks "
        f"in parallel (max concurrent: {max_concurrent})"
    )

    tasks = [process_with_limit(chunk_data) for chunk_data in large_chunks_data]
    results = await asyncio.gather(*tasks)

    logger.debug(
        f"🔄 CHUNKER_SEMANTIC_SUMMARY [{entity_context}] Applied semantic chunking to "
        f"{large_chunk_count} large chunks in parallel"
    )

    return dict(results)


async def _process_single_large_chunk(
    chunk_data: tuple, semantic_chunker, entity_context: str, logger: ContextualLogger
) -> tuple:
    """Process a single large chunk using semantic chunking."""
    idx, chunk = chunk_data

    logger.debug(
        f"✂️  CHUNKER_SEMANTIC_SPLIT [{entity_context}] Processing large chunk {idx + 1} "
        f"({chunk.token_count} tokens)"
    )

    chunk_start = asyncio.get_event_loop().time()

    # Perform semantic chunking with fallback
    semantic_chunks = await run_in_thread_pool(
        _semantic_chunk_with_fallback, semantic_chunker, chunk.text, entity_context, logger
    )

    chunk_elapsed = asyncio.get_event_loop().time() - chunk_start

    logger.debug(
        f"📦 CHUNKER_SEMANTIC_RESULT [{entity_context}] Large chunk {idx + 1} split into "
        f"{len(semantic_chunks)} semantic chunks in {chunk_elapsed:.3f}s"
    )

    return idx, [sc.text for sc in semantic_chunks]


def _semantic_chunk_with_fallback(chunker, text, context, logger: ContextualLogger):
    """Perform semantic chunking with fallback for errors."""
    try:
        return chunker.chunk(text)
    except Exception as e:
        logger.error(f"💥 CHUNKER_SEMANTIC_ERROR [{context}] Semantic chunking failed: {str(e)}")
        # Fallback: split text manually
        return _fallback_chunk_split(text)


def _fallback_chunk_split(text: str):
    """Fallback method to split text when semantic chunking fails."""
    text_length = len(text)
    part_size = text_length // 3
    parts = [text[i : i + part_size] for i in range(0, text_length, part_size)]

    class MockChunk:
        def __init__(self, text):
            self.text = text

    return [MockChunk(part) for part in parts if part.strip()]


def _reconstruct_chunk_list(
    initial_chunks: list, small_chunks: list[str], large_chunk_results: dict
) -> list[str]:
    """Reconstruct the final chunk list maintaining original order."""
    final_chunk_texts = []
    large_chunk_indices = set(large_chunk_results.keys())
    small_chunk_iter = iter(small_chunks)

    for i in range(len(initial_chunks)):
        if i in large_chunk_indices:
            final_chunk_texts.extend(large_chunk_results[i])
        else:
            final_chunk_texts.append(next(small_chunk_iter))

    return final_chunk_texts


@transformer(name="File Chunker")
async def file_chunker(file: FileEntity, logger: ContextualLogger) -> list[ChunkEntity]:
    """Default file chunker that converts files to markdown chunks using Chonkie.

    This transformer:
    1. Takes a FileEntity as input
    2. Converts the file to markdown using AsyncMarkItDown (or reads directly if already markdown)
    3. Uses Chonkie for intelligent chunking with a two-step approach:
       - First uses RecursiveChunker with markdown rules
       - Then applies semantic chunking if chunks are too large
    4. Yields each chunk as a ChunkEntity
    5. Cleans up temporary files after processing

    Args:
        file: The FileEntity to process
        logger: The logger to use

    Returns:
        list[ParentEntity | ChunkEntity]: The processed chunks
    """
    entity_context = f"Entity({file.entity_id})"

    logger.debug(
        f"📄 CHUNKER_START [{entity_context}] Starting file chunking for: {file.name} "
        f"(type: {type(file).__name__})"
    )

    file_class = type(file)
    produced_entities: list[ChunkEntity] = []

    # Use unified chunk model that carries full file metadata
    UnifiedChunkClass = file_class.create_unified_chunk_model()

    try:
        # Process file content
        logger.debug(f"🔍 CHUNKER_PROCESS [{entity_context}] Processing file content")
        start_time = asyncio.get_event_loop().time()

        text_content = await _process_file_content(file, entity_context, logger)

        process_elapsed = asyncio.get_event_loop().time() - start_time

        if not text_content or not text_content.strip():
            logger.warning(f"📭 CHUNKER_EMPTY [{entity_context}] No text content found")
            return []

        content_length = len(text_content)
        logger.debug(
            f"📊 CHUNKER_CONTENT [{entity_context}] Processed {content_length} characters "
            f"in {process_elapsed:.2f}s"
        )

        # Chunk the content
        logger.debug(f"✂️  CHUNKER_SPLIT_START [{entity_context}] Starting text chunking")
        chunk_start = asyncio.get_event_loop().time()

        final_chunk_texts = await _chunk_text_content(text_content, entity_context, logger)

        chunk_elapsed = asyncio.get_event_loop().time() - chunk_start
        logger.debug(
            f"📦 CHUNKER_SPLIT_DONE [{entity_context}] Created {len(final_chunk_texts)} chunks "
            f"in {chunk_elapsed:.2f}s"
        )

        # Create entities (unified chunks that include all file metadata)
        logger.debug(
            f"🏗️  CHUNKER_ENTITIES_START [{entity_context}] Creating unified chunk entities"
        )

        for i, chunk_text in enumerate(final_chunk_texts):
            if not chunk_text.strip():
                continue

            # Prepare chunk metadata with web-specific information if available
            chunk_metadata = {
                "chunk_index": i,
                "total_chunks": len(final_chunk_texts),
            }

            # If this is a WebFileEntity, add web-specific metadata
            md_parent_url = None
            if hasattr(file, "original_url") and file.original_url:
                md_parent_url = file.original_url
                chunk_metadata.update(
                    {
                        "original_url": file.original_url,
                        "web_title": getattr(file, "web_title", None),
                        "web_description": getattr(file, "web_description", None),
                        "crawl_metadata": getattr(file, "crawl_metadata", {}),
                    }
                )

            # Build base data from file so each chunk carries full metadata
            base_data = file.model_dump()
            base_data.update(
                {
                    "entity_id": file.entity_id,
                    "parent_entity_id": file.entity_id,
                    "md_content": chunk_text,
                    "md_type": "text",
                    "md_position": i,
                    "md_parent_title": file.name,
                    "md_parent_url": md_parent_url,
                    "metadata": chunk_metadata,
                }
            )

            chunk = UnifiedChunkClass(**base_data)
            produced_entities.append(chunk)

        total_elapsed = asyncio.get_event_loop().time() - start_time
        logger.debug(
            f"✅ CHUNKER_COMPLETE [{entity_context}] Chunking completed in {total_elapsed:.2f}s "
            f"({len(final_chunk_texts)} unified chunks)"
        )

        # Mark entity as fully processed in storage
        if file.airweave_system_metadata.sync_id:
            from airweave.platform.storage import storage_manager

            # Check if this is a CTTI entity - they don't need marking as processed
            # since they use global deduplication in the aactmarkdowns container
            if not storage_manager._is_ctti_entity(file):
                await storage_manager.mark_entity_processed(
                    logger,
                    file.airweave_system_metadata.sync_id,
                    file.entity_id,
                    len(final_chunk_texts),
                )
                logger.debug(
                    f"📝 CHUNKER_MARKED_PROCESSED [{entity_context}] "
                    f"Marked entity as fully processed with {len(final_chunk_texts)} chunks"
                )
            else:
                logger.debug(
                    f"🏥 CHUNKER_CTTI_SKIP_MARK [{entity_context}] "
                    f"Skipping mark_processed for CTTI entity (uses global deduplication)"
                )

    except Exception as e:
        # Log unsupported file types as warnings, not errors
        if isinstance(e, ValueError) and "Unsupported file type" in str(e):
            logger.warning(f"⚠️ CHUNKER_WARNING [{entity_context}] Unsupported file type: {str(e)}")
        else:
            logger.error(
                f"💥 CHUNKER_ERROR [{entity_context}] Chunking failed: {type(e).__name__}: {str(e)}"
            )
        raise e
    finally:
        # Clean up temporary file if it exists
        if hasattr(file, "airweave_system_metadata") and file.airweave_system_metadata.local_path:
            from airweave.platform.storage import storage_manager

            await storage_manager.cleanup_temp_file(
                logger, file.airweave_system_metadata.local_path
            )
            logger.debug(
                f"🧹 CHUNKER_CLEANUP [{entity_context}] Cleaned up temp file:"
                f"{file.airweave_system_metadata.local_path}"
            )

    return produced_entities
