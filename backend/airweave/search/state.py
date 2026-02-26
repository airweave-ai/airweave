"""Typed search state model.

Defines the SearchState Pydantic model that replaces the untyped dict
used to pass state between search operations.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchState(BaseModel):
    """Typed state passed between search operations.

    This model provides type safety for the state dict that flows through
    the search pipeline. Each operation reads from and writes to specific
    fields in this state.

    The state is initialized by the orchestrator and updated by each operation:
    - QueryExpansion -> expanded_queries
    - QueryInterpretation -> interpreted_filter
    - EmbedQuery -> dense_embeddings, sparse_embeddings
    - AccessControlFilter -> acl_filter, access_principals, filter (merged)
    - UserFilter -> filter (merged from user + interpreted + acl)
    - Retrieval -> results
    - FederatedSearch -> results (extended)
    - Reranking -> results (reordered)
    - GenerateAnswer -> completion
    """

    # =========================================================================
    # Query expansion results
    # =========================================================================
    expanded_queries: Optional[List[str]] = Field(
        default=None, description="Alternative query phrasings from query expansion"
    )

    # =========================================================================
    # Embeddings from EmbedQuery
    # =========================================================================
    dense_embeddings: Optional[List[List[float]]] = Field(
        default=None, description="Dense embeddings for neural search"
    )
    sparse_embeddings: Optional[List[Any]] = Field(
        default=None, description="Sparse embeddings for keyword search"
    )

    # =========================================================================
    # Filter components
    # =========================================================================
    interpreted_filter: Optional[Dict[str, Any]] = Field(
        default=None, description="Filter extracted from natural language query"
    )
    acl_filter: Optional[Dict[str, Any]] = Field(
        default=None, description="Access control filter from ACL operation"
    )
    filter: Optional[Dict[str, Any]] = Field(
        default=None, description="Final merged filter (user + interpreted + acl)"
    )

    # =========================================================================
    # Access control
    # =========================================================================
    access_principals: Optional[List[str]] = Field(
        default=None,
        description="Resolved access principals for the user (None = no AC sources)",
    )

    # =========================================================================
    # Search results (serialized AirweaveSearchResult dicts)
    # =========================================================================
    results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Search results as dicts"
    )

    # =========================================================================
    # Generated answer
    # =========================================================================
    completion: Optional[str] = Field(default=None, description="Generated natural language answer")

    # =========================================================================
    # Internal tracking fields
    # =========================================================================
    operation_metrics: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Metrics collected by operations"
    )
    provider_usage: Dict[str, str] = Field(
        default_factory=dict, description="Which provider succeeded for each operation"
    )
    failed_federated_auth: List[str] = Field(
        default_factory=list, description="Source connection IDs that failed federated auth"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
