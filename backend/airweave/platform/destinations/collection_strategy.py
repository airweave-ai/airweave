"""Physical collection naming for Qdrant multi-tenancy.

All collections now use shared physical collections in Qdrant:
- 384-dim vectors → airweave_shared_minilm_l6_v2 (local model)
- 1536-dim vectors → airweave_shared_text_embedding_3_small (OpenAI)
- 3072-dim vectors → airweave_shared_text_embedding_3_large (OpenAI)

Tenant isolation is achieved via airweave_collection_id payload filtering.
"""

from airweave.core.config import settings


def get_default_vector_size() -> int:
    """Auto-detect vector size based on embedding model configuration.

    Returns:
        3072 if OpenAI API key is set (text-embedding-3-large)
        384 otherwise (MiniLM-L6-v2)
    """
    return 3072 if settings.OPENAI_API_KEY else 384


def get_physical_collection_name(vector_size: int | None = None) -> str:
    """Get physical Qdrant collection name based on vector size.

    Args:
        vector_size: Vector dimensions. Auto-detected if None:
                     - 3072 if OpenAI API key is set (text-embedding-3-large)
                     - 384 otherwise (MiniLM-L6-v2)

    Returns:
        Physical collection name in Qdrant:
        - "airweave_shared_text_embedding_3_large" for 3072-dim vectors
        - "airweave_shared_text_embedding_3_small" for 1536-dim vectors
        - "airweave_shared_minilm_l6_v2" for 384-dim vectors (default for other sizes)
    """
    if vector_size is None:
        vector_size = get_default_vector_size()

    if vector_size == 3072:
        return "airweave_shared_text_embedding_3_large"
    elif vector_size == 1536:
        return "airweave_shared_text_embedding_3_small"
    else:
        return "airweave_shared_minilm_l6_v2"


def get_openai_embedding_model_for_vector_size(vector_size: int) -> str:
    """Get OpenAI embedding model name for given vector dimensions.

    Args:
        vector_size: Vector dimensions (3072 or 1536)

    Returns:
        - "text-embedding-3-large" for 3072-dim
        - "text-embedding-3-small" for 1536-dim

    Raises:
        ValueError: For vector sizes that don't use OpenAI models (e.g., 384 uses local model)
    """
    if vector_size == 3072:
        return "text-embedding-3-large"
    elif vector_size == 1536:
        return "text-embedding-3-small"
    else:
        raise ValueError(
            f"No OpenAI model for vector_size {vector_size}. Only 3072 and 1536 use OpenAI models."
        )
