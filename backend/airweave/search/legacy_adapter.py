"""Adapter for converting between legacy and new search schemas.

This module provides backwards compatibility by converting old search
request/response formats to the new implementation.
"""

from airweave.schemas.search import SearchRequest, SearchResponse
from airweave.schemas.search_legacy import (
    LegacySearchRequest,
    LegacySearchResponse,
    QueryExpansionStrategy,
    ResponseType,
    SearchStatus,
)


def convert_legacy_request_to_new(legacy_request: LegacySearchRequest) -> SearchRequest:
    """Convert legacy SearchRequest to new SearchRequest format.

    Args:
        legacy_request: Legacy search request with old parameter names

    Returns:
        New search request with updated parameter names
    """
    # Map search_method to retrieval_strategy
    retrieval_strategy = None
    if legacy_request.search_method:
        retrieval_strategy = legacy_request.search_method  # Values are compatible

    # Map expansion_strategy to expand_query boolean
    expand_query = None
    if legacy_request.expansion_strategy is not None:
        if legacy_request.expansion_strategy == QueryExpansionStrategy.NO_EXPANSION:
            expand_query = False
        else:
            # AUTO or LLM both mean "enable expansion"
            expand_query = True

    # Map enable_reranking to rerank
    rerank = legacy_request.enable_reranking

    # Map enable_query_interpretation to interpret_filters
    interpret_filters = legacy_request.enable_query_interpretation

    # Map response_type to generate_answer
    generate_answer = None
    if legacy_request.response_type == ResponseType.COMPLETION:
        generate_answer = True
    elif legacy_request.response_type == ResponseType.RAW:
        generate_answer = False

    return SearchRequest(
        query=legacy_request.query,
        retrieval_strategy=retrieval_strategy,
        filter=legacy_request.filter,
        offset=legacy_request.offset,
        limit=legacy_request.limit,
        expand_query=expand_query,
        interpret_filters=interpret_filters,
        rerank=rerank,
        generate_answer=generate_answer,
    )


def convert_new_response_to_legacy(
    new_response: SearchResponse,
    requested_response_type: ResponseType,
) -> LegacySearchResponse:
    """Convert new SearchResponse to legacy SearchResponse format.

    Args:
        new_response: New search response from the service
        requested_response_type: The response type requested by the client

    Returns:
        Legacy search response with status and response_type fields
    """
    # Determine status based on results
    if not new_response.results or len(new_response.results) == 0:
        status = SearchStatus.NO_RESULTS
    else:
        # Check if results are relevant (have reasonable scores)
        # For backwards compatibility, assume success if we have results
        status = SearchStatus.SUCCESS

    return LegacySearchResponse(
        results=new_response.results,
        response_type=requested_response_type,
        completion=new_response.completion,
        status=status,
    )
