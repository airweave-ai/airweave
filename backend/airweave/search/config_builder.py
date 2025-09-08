"""Search configuration builder.

This module builds a SearchConfig from a SearchRequest, creating the execution
plan with the appropriate operations based on the request parameters.

IMPORTANT: These defaults are designed for optimal search quality out of the box.
Most users should not need to change them unless they have specific requirements.
"""

from airweave.api.context import ApiContext
from airweave.schemas.search import (
    QueryExpansionStrategy,
    ResponseType,
    SearchConfig,
    SearchRequest,
)
from airweave.search.operations import (
    CompletionGeneration,
    Embedding,
    LLMReranking,
    QdrantFilterOperation,
    QueryExpansion,
    QueryInterpretation,
    RecencyBias,
    VectorSearch,
)

# ============================================================================
# SEARCH DEFAULTS - Single source of truth for all default values
# ============================================================================

# Core search defaults
DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0
DEFAULT_SCORE_THRESHOLD = None  # No threshold by default
DEFAULT_SEARCH_METHOD = "hybrid"  # Combines neural + BM25

# Recency defaults
DEFAULT_RECENCY_BIAS = 0.3
DEFAULT_DATETIME_FIELD_HINT = "airweave_system_metadata.airweave_updated_at"

# Operation defaults
DEFAULT_EXPANSION_STRATEGY = QueryExpansionStrategy.AUTO  # Up to 4 variants
DEFAULT_QUERY_INTERPRETATION = False  # DISABLED by default
DEFAULT_RERANKING = True  # ENABLED by default
DEFAULT_RESPONSE_TYPE = ResponseType.RAW  # Raw results, not completion

# ============================================================================


class SearchConfigBuilder:
    """Builds SearchConfig with operations from SearchRequest.

    This builder analyzes the SearchRequest and creates a SearchConfig
    with the appropriate operations configured and assigned to their
    specific fields.
    """

    def build(
        self, search_request: SearchRequest, collection_id: str, ctx: ApiContext
    ) -> SearchConfig:
        """Build SearchConfig from SearchRequest.

        This method:
        1. Extracts parameters from the request
        2. Applies defaults for missing values
        3. Creates and configures appropriate operations
        4. Returns SearchConfig with operations assigned to fields

        Args:
            search_request: User's search request
            collection_id: ID of the collection to search
            ctx: API context for logging

        Returns:
            SearchConfig with operations configured
        """
        ctx.logger.info(
            f"Building search config for query: '{search_request.query[:50]}...', "
            f"collection: {collection_id}"
        )

        # Apply defaults first
        search_method = search_request.search_method or DEFAULT_SEARCH_METHOD

        # Build the operations based on request
        ops = self._create_operations(search_request, search_method, ctx)

        # Log which operations are enabled
        enabled_ops = []
        if ops["query_interpretation"]:
            enabled_ops.append("query_interpretation")
        if ops["query_expansion"]:
            enabled_ops.append("query_expansion")
        if ops["qdrant_filter"]:
            enabled_ops.append("qdrant_filter")
        enabled_ops.extend(["embedding", "vector_search"])  # Always present
        if ops["recency"]:
            enabled_ops.append("recency")
        if ops["reranking"]:
            enabled_ops.append(f"reranking({ops['reranking'].name})")
        if ops["completion"]:
            enabled_ops.append("completion")

        ctx.logger.info(f"Enabled operations: {enabled_ops}")

        # Apply defaults for all parameters using the constants
        # Use explicit None checks to handle 0 values correctly
        limit = search_request.limit if search_request.limit is not None else DEFAULT_LIMIT
        offset = search_request.offset if search_request.offset is not None else DEFAULT_OFFSET
        score_threshold = search_request.score_threshold  # DEFAULT_SCORE_THRESHOLD (None is valid)

        # Public recency_bias (0..1) controls dynamic post-retrieval recency operator
        recency_bias = (
            search_request.recency_bias
            if getattr(search_request, "recency_bias", None) is not None
            else DEFAULT_RECENCY_BIAS
        )
        # No static DecayConfig; RecencyBias operator derives decay at runtime

        # Create the config with operations as fields
        config = SearchConfig(
            # Core parameters with defaults
            query=search_request.query,
            collection_id=collection_id,
            limit=limit,
            offset=offset,
            score_threshold=score_threshold,
            # Hybrid search and recency parameters
            search_method=search_method,
            recency_bias=recency_bias,
            # Operations as fields
            query_interpretation=ops["query_interpretation"],
            query_expansion=ops["query_expansion"],
            qdrant_filter=ops["qdrant_filter"],
            embedding=ops["embedding"],
            vector_search=ops["vector_search"],
            # Recency operator instance and knob
            recency=ops["recency"],
            reranking=ops["reranking"],
            completion=ops["completion"],
        )

        return config

    def _create_operations(
        self, search_request: SearchRequest, search_method: str, ctx: ApiContext
    ) -> dict:
        """Create operations based on request parameters.

        Returns a dictionary with operation instances or None for each field.

        Args:
            search_request: User's search request
            search_method: The search method to use (already defaulted)
            ctx: API context for logging

        Returns:
            Dictionary with operation instances keyed by field name
        """
        ops = {}

        # ========== Query Interpretation (Optional) ==========
        if self._should_enable_query_interpretation(search_request):
            ctx.logger.debug("Enabling query interpretation")
            ops["query_interpretation"] = QueryInterpretation()
        else:
            ops["query_interpretation"] = None

        # ========== Query Expansion (Optional) ==========
        # Apply default expansion strategy if not specified
        expansion_strategy = search_request.expansion_strategy
        if expansion_strategy is None:
            expansion_strategy = DEFAULT_EXPANSION_STRATEGY

        if expansion_strategy != QueryExpansionStrategy.NO_EXPANSION:
            ctx.logger.debug(f"Enabling query expansion with strategy: {expansion_strategy}")
            ops["query_expansion"] = QueryExpansion(strategy=expansion_strategy, max_expansions=4)
        else:
            ops["query_expansion"] = None

        # ========== Qdrant Filter (Optional) ==========
        if search_request.filter:
            ctx.logger.debug("Enabling Qdrant filter")
            # Store the filter dict in the operation
            filter_op = QdrantFilterOperation()
            # Store the filter dict for the operation to use
            filter_op.filter_dict = (
                search_request.filter.model_dump(exclude_none=True)
                if search_request.filter
                else None
            )
            ops["qdrant_filter"] = filter_op
        else:
            ops["qdrant_filter"] = None

        # ========== Core Operations (Always Required) ==========
        ctx.logger.debug(
            f"Adding core operations: embedding, vector_search with search_method={search_method}"
        )
        ops["embedding"] = Embedding(search_method=search_method)
        ops["vector_search"] = VectorSearch(search_method=search_method)

        # ========== Dynamic Recency (Optional) ==========
        # Get recency bias with default
        recency_bias = (
            search_request.recency_bias
            if getattr(search_request, "recency_bias", None) is not None
            else DEFAULT_RECENCY_BIAS
        )

        # Enable when bias is positive
        if recency_bias > 0:
            ctx.logger.debug(f"Enabling recency operator with bias={recency_bias}")
            ops["recency"] = RecencyBias(datetime_field=DEFAULT_DATETIME_FIELD_HINT)
        else:
            ops["recency"] = None

        # ========== Reranking (Optional) ==========
        if self._should_enable_reranking(search_request):
            ctx.logger.debug("Enabling LLM reranking")
            ops["reranking"] = LLMReranking()
        else:
            ops["reranking"] = None

        # ========== Completion (Optional) ==========
        # Apply default response type if not specified
        response_type = search_request.response_type
        if response_type is None:
            response_type = DEFAULT_RESPONSE_TYPE

        if response_type == ResponseType.COMPLETION:
            ctx.logger.debug("Enabling completion generation")
            ops["completion"] = CompletionGeneration(
                default_model="gpt-5-nano", max_results_context=100
            )
        else:
            ops["completion"] = None

        return ops

    def _should_enable_query_interpretation(self, search_request: SearchRequest) -> bool:
        """Determine if query interpretation should be enabled.

        Args:
            search_request: User's search request

        Returns:
            Whether to enable query interpretation
        """
        # Use DEFAULT_QUERY_INTERPRETATION if not specified
        if search_request.enable_query_interpretation is None:
            return DEFAULT_QUERY_INTERPRETATION
        return bool(search_request.enable_query_interpretation)

    def _should_enable_reranking(self, search_request: SearchRequest) -> bool:
        """Determine if reranking should be enabled.

        Args:
            search_request: User's search request

        Returns:
            Whether to enable reranking
        """
        # Use DEFAULT_RERANKING if not specified
        if search_request.enable_reranking is None:
            return DEFAULT_RERANKING
        return bool(search_request.enable_reranking)
