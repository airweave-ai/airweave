"""Code file chunker."""

from copy import deepcopy
from typing import List

from chonkie import CodeChunker

from airweave.platform.decorators import transformer
from airweave.platform.entities._base import CodeFileEntity
from airweave.platform.transformers.utils import MAX_CHUNK_SIZE, count_tokens


@transformer(name="Code File Chunker")
async def code_file_chunker(file: CodeFileEntity) -> List[CodeFileEntity]:
    """Chunk a code file.

    This transformer:
    1. Takes a CodeFileEntity as input
    2. Uses Chonkie to chunk the code file if size is greater than 8191 tokens
    3. Yields each chunk as a CodeFileEntity

    Args:
        file: The CodeFileEntity to process

    Returns:
        List[CodeFileEntity]: The processed chunks
    """
    # If file.content is None, return empty list
    if file.content is None:
        return []

    # If the entire entity is small enough, return it as is
    if count_tokens(file.model_dump_json()) <= MAX_CHUNK_SIZE - 191:
        return [file]

    # Create a CodeChunker with appropriate parameters
    code_chunker = CodeChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=MAX_CHUNK_SIZE - 2000,  # Leave room for metadata
    )

    # Get chunks from the code content
    chunks = code_chunker.chunk(file.content)

    if not chunks:  # If chunking failed or returned empty, return original
        return [file]

    # Create a new CodeFileEntity for each chunk
    chunked_files = []
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        # Create a deep copy of the original file
        chunked_file = deepcopy(file)

        # Update the content with just this chunk
        chunked_file.content = chunk.text

        # Add chunk metadata to entity metadata
        if chunked_file.metadata is None:
            chunked_file.metadata = {}

        chunked_file.metadata.update(
            {
                "chunk_index": idx + 1,
                "total_chunks": total_chunks,
                "original_file_id": file.file_id,
                "chunk_start_index": chunk.start_index,
                "chunk_end_index": chunk.end_index,
            }
        )

        # Update name to indicate it's a chunk
        chunked_file.name = f"{file.name} (Chunk {idx + 1}/{total_chunks})"

        chunked_files.append(chunked_file)

    return chunked_files
