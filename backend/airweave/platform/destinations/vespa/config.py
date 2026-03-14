"""Vespa destination configuration constants.

Single source of truth for all Vespa-related settings.
"""

# =============================================================================
# Search Tuning
# =============================================================================

# Number of candidates retrieved per retrieval method (matches Qdrant's prefetch_limit)
TARGET_HITS = 5000

# Extra HNSW graph exploration for better recall with pre-filtering
HNSW_EXPLORE_ADDITIONAL = 500

# Final RRF output count (no second phase needed with bfloat16)
GLOBAL_PHASE_RERANK_COUNT = 100

# =============================================================================
# Embedding Configuration
# =============================================================================

# Expected embedding dimensions (text-embedding-3-large)
VESPA_EMBEDDING_DIM = 3072

# =============================================================================
# Feed Settings (bulk_insert)
# =============================================================================

FEED_MAX_QUEUE_SIZE = 500
FEED_MAX_WORKERS = 16
FEED_MAX_CONNECTIONS = 16

# =============================================================================
# Delete Settings
# =============================================================================

# Max parent IDs per query batch in bulk_delete_by_parent_ids
DELETE_BATCH_SIZE = 200

# Max concurrent direct-delete HTTP requests (semaphore limit)
DELETE_CONCURRENCY = 20

# Max doc IDs to resolve per YQL query (Vespa query result limit)
DELETE_QUERY_HITS_LIMIT = 10000

# =============================================================================
# Vespa Schema Names
# =============================================================================

# All Vespa schemas (derived from entity class hierarchy)
ALL_VESPA_SCHEMAS = [
    "base_entity",
    "file_entity",
    "code_file_entity",
    "email_entity",
    "web_entity",
]
