"""Tests for the code file chunker transformer."""

from datetime import datetime
import uuid
import pytest

from airweave.platform.entities._base import CodeFileEntity
from airweave.platform.transformers.code_file_chunker import code_file_chunker
from airweave.platform.transformers.utils import MAX_CHUNK_SIZE, count_tokens


def generate_large_code_content(min_size):
    """Generate a Python file content that's guaranteed to be larger than min_size tokens."""
    function_template = """
def function{num}(param1, param2, param3):
    \"\"\"
    This is a detailed docstring for function number {num}.
    It performs a complex calculation with the provided parameters.

    Args:
        param1: The first parameter
        param2: The second parameter
        param3: The third parameter

    Returns:
        A calculated result based on the parameters
    \"\"\"
    # Initialize an accumulator
    accumulator = 0

    # Perform a complex calculation
    for i in range(param1):
        for j in range(param2):
            accumulator += i * j * param3

    # Create a large result object
    result = {{
        "function_number": {num},
        "calculation_result": accumulator,
        "input_params": {{
            "param1": param1,
            "param2": param2,
            "param3": param3
        }},
        "metadata": {{
            "created_at": "2023-06-01T12:00:00Z",
            "version": "1.0.0",
            "is_valid": True
        }}
    }}

    return result

"""
    content = ""
    size = 0

    # Keep adding functions until we exceed the required size
    i = 0
    test_entity = CodeFileEntity(
        entity_id=str(uuid.uuid4()),
        breadcrumbs=[],
        source_name="test",
        name="test.py",
        file_id="test123",
        size=0,
        path_in_repo="test.py",
        repo_name="test-repo",
        repo_owner="test-owner",
        url="https://example.com/test.py",
        content=content,
        language="python",
    )

    # Add functions until the file is large enough
    while size <= min_size and i < 200:  # Cap at 200 functions to prevent infinite loops
        content += function_template.format(num=i)
        test_entity.content = content
        test_entity.size = len(content)
        size = count_tokens(test_entity.model_dump_json())
        i += 1

    if size <= min_size:
        pytest.skip(f"Could not generate content large enough: {size} < {min_size}")

    return content


@pytest.mark.asyncio
class TestCodeFileChunker:
    """Test the code file chunker transformer."""

    async def test_empty_content(self):
        """Test that an empty content returns an empty list."""
        file = CodeFileEntity(
            entity_id=str(uuid.uuid4()),
            breadcrumbs=[],
            source_name="test",
            name="test.py",
            file_id="test123",
            size=0,
            path_in_repo="test.py",
            repo_name="test-repo",
            repo_owner="test-owner",
            url="https://example.com/test.py",
            content=None,
            language="python",
        )

        result = await code_file_chunker(file)
        assert result == []

    async def test_small_file_unchanged(self):
        """Test that a small file is returned unchanged."""
        content = "def hello_world():\n    print('Hello, world!')"
        file = CodeFileEntity(
            entity_id=str(uuid.uuid4()),
            breadcrumbs=[],
            source_name="test",
            name="test.py",
            file_id="test123",
            size=len(content),
            path_in_repo="test.py",
            repo_name="test-repo",
            repo_owner="test-owner",
            url="https://example.com/test.py",
            content=content,
            language="python",
        )

        # If the entity is small, it should be returned unchanged
        entity_size = count_tokens(file.model_dump_json())
        if entity_size <= MAX_CHUNK_SIZE - 191:
            result = await code_file_chunker(file)
            assert len(result) == 1
            assert result[0] == file
        else:
            pytest.skip("Test file unexpectedly too large for small file test")

    async def test_large_file_chunked(self):
        """Test that a large file is properly chunked by the real CodeChunker."""
        # Create a large Python file that exceeds the chunk size limit
        threshold = MAX_CHUNK_SIZE - 190  # Just over the limit
        large_content = generate_large_code_content(threshold)

        file = CodeFileEntity(
            entity_id=str(uuid.uuid4()),
            breadcrumbs=[],
            source_name="test",
            name="test.py",
            file_id="test123",
            size=len(large_content),
            path_in_repo="test.py",
            repo_name="test-repo",
            repo_owner="test-owner",
            url="https://example.com/test.py",
            content=large_content,
            language="python",
            last_modified=datetime.now(),
            commit_id="abc123",
        )

        # Process with the real code chunker
        result = await code_file_chunker(file)

        # Verify chunking happened
        assert len(result) > 1

        # Verify basic metadata is consistent across chunks
        for chunk_file in result:
            assert chunk_file.file_id == file.file_id
            assert chunk_file.source_name == file.source_name
            assert chunk_file.repo_name == file.repo_name
            assert chunk_file.language == file.language

            # Verify chunk metadata exists
            assert "chunk_index" in chunk_file.metadata
            assert "total_chunks" in chunk_file.metadata
            assert "original_file_id" in chunk_file.metadata
            assert "chunk_start_index" in chunk_file.metadata
            assert "chunk_end_index" in chunk_file.metadata

            # Verify each chunk has the right name format
            chunk_idx = chunk_file.metadata["chunk_index"]
            total_chunks = chunk_file.metadata["total_chunks"]
            assert chunk_file.name == f"{file.name} (Chunk {chunk_idx}/{total_chunks})"

            # Verify each chunk is small enough to fit in the model
            chunk_size = count_tokens(chunk_file.model_dump_json())
            assert chunk_size < MAX_CHUNK_SIZE - 191

    async def test_metadata_preservation(self):
        """Test that existing metadata is preserved when chunking."""
        # Create a large Python file with metadata
        threshold = MAX_CHUNK_SIZE - 190  # Just over the limit
        large_content = generate_large_code_content(threshold)

        # Create file with existing metadata
        file = CodeFileEntity(
            entity_id=str(uuid.uuid4()),
            breadcrumbs=[],
            source_name="test",
            name="test_with_metadata.py",
            file_id="meta123",
            size=len(large_content),
            path_in_repo="test_with_metadata.py",
            repo_name="test-repo",
            repo_owner="test-owner",
            url="https://example.com/test_with_metadata.py",
            content=large_content,
            language="python",
            metadata={"existing_key": "existing_value", "another_key": 42, "important_flag": True},
        )

        # Process with the real code chunker
        result = await code_file_chunker(file)

        # Verify chunking happened
        assert len(result) > 1

        # Verify original metadata is preserved in all chunks
        for chunk_file in result:
            assert chunk_file.metadata["existing_key"] == "existing_value"
            assert chunk_file.metadata["another_key"] == 42
            assert chunk_file.metadata["important_flag"] is True
