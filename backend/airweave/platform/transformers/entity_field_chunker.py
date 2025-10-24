"""Entity chunker for chunking large embeddable text in ChunkEntity instances."""

from typing import Any, Dict, List, Optional

from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules, TokenChunker

from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities._base_legacy import ChunkEntity
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.transformers.utils import (
    count_tokens,
)

# Cache for chunkers
_token_chunker_cache = {}
_recursive_chunker = None

# Token limits for embeddable text
# OpenAI's limit is 8191 tokens, but embeddable_text is already capped at 12000 chars
# We use a conservative token limit to ensure we stay under API limits
SAFE_EMBEDDABLE_TOKEN_SIZE = 6000  # Conservative limit for embeddable text
TARGET_CHUNK_TOKEN_SIZE = 3000  # Target size for each chunk when splitting


def get_token_chunker(chunk_size: int) -> TokenChunker:
    """Get or create a token chunker with the specified chunk size.

    Args:
        chunk_size: Target size for each chunk

    Returns:
        Configured TokenChunker
    """
    global _token_chunker_cache

    if chunk_size not in _token_chunker_cache:
        _token_chunker_cache[chunk_size] = TokenChunker(
            tokenizer=count_tokens,  # Fixed: API changed from tokenizer_or_token_counter
            chunk_size=chunk_size,
            chunk_overlap=100,  # Small overlap for context
        )

    return _token_chunker_cache[chunk_size]


def get_recursive_chunker(chunk_size: int) -> RecursiveChunker:
    """Get or create a recursive chunker optimized for text fields.

    Args:
        chunk_size: Target size for each chunk

    Returns:
        Configured RecursiveChunker
    """
    # Simpler rules optimized for general text content
    rules = RecursiveRules(
        [
            RecursiveLevel(delimiters=["\n\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n"], include_delim="next"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            RecursiveLevel(delimiters=[", "], include_delim="prev"),
        ]
    )

    return RecursiveChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=chunk_size,
        rules=rules,
        min_characters_per_chunk=50,
    )


def calculate_embeddable_text_size(entity: ChunkEntity) -> int:
    """Calculate the token size of the embeddable text.

    Args:
        entity: The ChunkEntity to measure

    Returns:
        Token count of the embeddable text
    """
    # Build the embeddable text and count its tokens
    embeddable_text = entity.build_embeddable_text()
    return count_tokens(embeddable_text)


def get_embeddable_fields(entity: ChunkEntity) -> Dict[str, Any]:
    """Get fields marked as embeddable from the entity.

    Args:
        entity: The ChunkEntity to examine

    Returns:
        Dictionary of field names to values for embeddable fields
    """
    embeddable_fields = {}

    # Get field names marked as embeddable
    field_names = entity._get_embeddable_fields()

    # If no explicit embeddable fields, check common content fields
    if not field_names:
        # Check for common content fields that contribute to embeddable text
        common_fields = ["md_content", "content", "text", "description", "summary", "notes"]
        field_names = [f for f in common_fields if hasattr(entity, f)]

    # Collect the values
    for field_name in field_names:
        value = getattr(entity, field_name, None)
        if value is not None and isinstance(value, str) and value.strip():
            embeddable_fields[field_name] = value

    return embeddable_fields


def find_largest_embeddable_field(entity: ChunkEntity) -> Optional[tuple[str, str, int]]:
    """Find the largest embeddable field to chunk.

    Args:
        entity: The ChunkEntity to examine

    Returns:
        Tuple of (field_name, field_value, token_size) or None if no chunkable field
    """
    embeddable_fields = get_embeddable_fields(entity)

    if not embeddable_fields:
        return None

    largest_field = None
    largest_value = None
    largest_size = 0

    for field_name, field_value in embeddable_fields.items():
        size = count_tokens(field_value)
        if size > largest_size:
            largest_field = field_name
            largest_value = field_value
            largest_size = size

    return (largest_field, largest_value, largest_size) if largest_field else None


def _clean_text_for_chunking(text: str, logger: ContextualLogger) -> str:
    """Clean text by removing problematic Unicode characters."""
    zero_width_chars = [
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\u200e",  # Left-to-right mark
        "\u200f",  # Right-to-left mark
        "\ufeff",  # Zero-width no-break space
        "\u00a0",  # Non-breaking space (replace with regular space)
    ]

    cleaned_text = text
    for char in zero_width_chars:
        if char in cleaned_text:
            count = cleaned_text.count(char)
            if count > 10:  # Only log if significant
                logger.debug(f"Removing {count} instances of Unicode {ord(char):04X} from text")
            # Replace non-breaking space with regular space instead of removing
            if char == "\u00a0":
                cleaned_text = cleaned_text.replace(char, " ")
            else:
                cleaned_text = cleaned_text.replace(char, "")

    # Also collapse multiple spaces into single space
    import re

    cleaned_text = re.sub(r"\s+", " ", cleaned_text)
    return cleaned_text


def _create_truncated_chunk(chunk, target_chunk_size: int):
    """Create a truncated chunk when original is too large."""
    max_chars = int(len(chunk.text) * target_chunk_size / count_tokens(chunk.text))
    truncated_text = chunk.text[:max_chars]

    # Create a simple chunk-like object with truncated text
    class SimpleChunk:
        def __init__(self, text):
            self.text = text
            self.start_index = 0
            self.end_index = len(text)

    return SimpleChunk(truncated_text)


def _validate_chunks(chunk_result, target_chunk_size: int, logger: ContextualLogger) -> List[Any]:
    """Post-process chunks to ensure none are too large."""
    validated_chunks = []
    for chunk in chunk_result:
        chunk_size = count_tokens(chunk.text)
        if chunk_size > target_chunk_size * 1.2:  # Allow 20% margin
            logger.warning(
                f"Chunk exceeded target size ({chunk_size} > {target_chunk_size * 1.2}). "
                f"Will truncate to fit."
            )
            truncated_chunk = _create_truncated_chunk(chunk, target_chunk_size)
            validated_chunks.append(truncated_chunk)
        else:
            validated_chunks.append(chunk)
    return validated_chunks


async def chunk_text_optimized(
    text: str, target_chunk_size: int, field_name: str, entity_id: str, logger: ContextualLogger
) -> List[Any]:
    """Chunk text using optimized token-based approach without embeddings.

    Args:
        text: Text to chunk
        target_chunk_size: Target size for each chunk
        field_name: Name of the field being chunked
        entity_id: Entity ID for logging
        logger: The logger to use

    Returns:
        List of chunks
    """
    # Clean text
    cleaned_text = _clean_text_for_chunking(text, logger)
    text_size = count_tokens(cleaned_text)

    logger.debug(
        f"Starting optimized chunking for field '{field_name}' in entity {entity_id} "
        f"(size: {text_size} tokens after cleaning, target chunk size: {target_chunk_size})"
    )

    # First try recursive chunking which respects text structure
    recursive_chunker = get_recursive_chunker(target_chunk_size)

    def _chunk_recursive(text: str):
        try:
            chunks = recursive_chunker.chunk(text)
            return chunks
        except Exception as e:
            logger.warning(
                f"Recursive chunking failed for field '{field_name}' in entity {entity_id}: "
                f"{str(e)}. Falling back to token chunking."
            )
            return None

    chunk_result = await run_in_thread_pool(_chunk_recursive, cleaned_text)

    if chunk_result is None:
        # Fallback to simple token chunking
        logger.debug(
            f"Using token chunker as fallback for field '{field_name}' in entity {entity_id}"
        )
        token_chunker = get_token_chunker(target_chunk_size)

        def _chunk_tokens(text: str):
            return token_chunker.chunk(text)

        chunk_result = await run_in_thread_pool(_chunk_tokens, cleaned_text)

    # Post-process chunks to ensure none are too large
    validated_chunks = _validate_chunks(chunk_result, target_chunk_size, logger)

    logger.debug(
        f"Chunking complete: {len(chunk_result)} original chunks → "
        f"{len(validated_chunks)} validated chunks"
    )

    return validated_chunks


@transformer(name="Entity Chunker")
async def entity_chunker(entity: BaseEntity, logger: ContextualLogger) -> List[BaseEntity]:
    """Chunk large embeddable text in ChunkEntity instances.

    This transformer ensures the embeddable text stays under token limits by:
    1. Checking if the entity is a ChunkEntity (only these have embeddable text)
    2. Calculating the embeddable text size
    3. If too large, chunking the largest embeddable field
    4. Creating multiple entities with smaller chunks

    Args:
        entity: The BaseEntity to process
        logger: The logger to use

    Returns:
        List[BaseEntity]: Either the original entity or multiple chunked entities
    """
    # Only process ChunkEntity instances (which have embeddable_text)
    if not isinstance(entity, ChunkEntity):
        logger.debug(f"Entity {entity.entity_id} is not a ChunkEntity, skipping chunking")
        return [entity]

    # Skip if already chunked
    if getattr(entity, "chunk_index", None) is not None:
        logger.debug(
            f"Entity {entity.entity_id} already chunked (index: {entity.chunk_index}), skipping"
        )
        return [entity]

    # Check embeddable text size
    embeddable_size = calculate_embeddable_text_size(entity)

    # If within limits, return as-is
    if embeddable_size <= SAFE_EMBEDDABLE_TOKEN_SIZE:
        return [entity]

    # Find the largest embeddable field to chunk
    field_info = find_largest_embeddable_field(entity)

    if not field_info:
        logger.warning(
            f"Entity {entity.entity_id} has large embeddable text ({embeddable_size} tokens) "
            f"but no chunkable fields found. Returning as-is."
        )
        return [entity]

    field_name, field_value, field_size = field_info

    logger.debug(
        f"Chunking field '{field_name}' ({field_size} tokens) in entity {entity.entity_id}"
    )

    # Chunk the field
    chunks = await chunk_text_optimized(
        field_value, TARGET_CHUNK_TOKEN_SIZE, field_name, entity.entity_id, logger
    )

    # Create new entities with chunked content
    output_entities = []
    entity_dict = entity.model_dump()

    for i, chunk in enumerate(chunks):
        # Create a copy with the chunked field
        new_dict = {
            **entity_dict,
            field_name: chunk.text,
            "chunk_index": i,
            "entity_id": f"{entity.entity_id}_chunk_{i}",
        }

        # Create new entity instance
        new_entity = type(entity)(**new_dict)

        # Verify the new entity's embeddable text is within limits
        new_size = calculate_embeddable_text_size(new_entity)
        if new_size > SAFE_EMBEDDABLE_TOKEN_SIZE:
            logger.warning(
                f"Chunk {i} still exceeds limit ({new_size} tokens), may need further processing"
            )

        # ➌ halve chunk size each recursion → exponential shrink
        tgt_chunk = int(max(300, field_size / 2 / 1.5))
        chunks = await chunk_text_optimized(
            field_value, tgt_chunk, field_name, entity.entity_id, logger
        )

    logger.debug(f"Created {len(output_entities)} chunks from entity {entity.entity_id}")

    return output_entities
