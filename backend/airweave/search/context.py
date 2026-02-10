"""Search context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from airweave.search.emitter import EventEmitter
    from airweave.search.operations import (
        AccessControlFilter,
        EmbedQuery,
        FederatedSearch,
        GenerateAnswer,
        QueryExpansion,
        QueryInterpretation,
        Reranking,
        Retrieval,
        UserFilter,
    )


class SearchContext(BaseModel):
    """Search context."""

    model_config = {"arbitrary_types_allowed": True}

    request_id: str = Field()
    collection_id: UUID = Field()
    readable_collection_id: str = Field()
    stream: bool = Field()
    vector_size: int = Field()
    # Pagination config available even if Retrieval operation is disabled
    offset: int = Field()
    limit: int = Field()

    query: str = Field()

    emitter: EventEmitter = Field()

    access_control_filter: Optional[AccessControlFilter] = Field()
    query_expansion: Optional[QueryExpansion] = Field()
    query_interpretation: Optional[QueryInterpretation] = Field()
    embed_query: Optional[EmbedQuery] = Field()
    user_filter: Optional[UserFilter] = Field()
    retrieval: Optional[Retrieval] = Field()
    federated_search: Optional[FederatedSearch] = Field()
    reranking: Optional[Reranking] = Field()
    generate_answer: Optional[GenerateAnswer] = Field()
