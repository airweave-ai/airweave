"""Physical collection naming for Qdrant multi-tenancy.

All collections now use shared physical collections in Qdrant:
- 384-dim vectors → airweave_shared_minilm_l6_v2 (local model)
- 1536-dim vectors → airweave_shared_text_embedding_3_small (OpenAI)

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
        - "airweave_shared_minilm_l6_v2" for 384-dim vectors (default for other sizes)
    """
    if vector_size is None:
        vector_size = get_default_vector_size()

    return (
        "airweave_shared_text_embedding_3_large"
        if vector_size == 3072
        else "airweave_shared_minilm_l6_v2"
    )
