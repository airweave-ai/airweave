"""V2 search query persistence.

Fire-and-forget helper that persists search queries from V2 search tiers
(instant, classic, agentic) into the search_queries table. Mirrors the V1
behaviour in airweave.search.helpers.persist_search_data but accepts V2
service-level data instead of a SearchContext.

Failures are logged and swallowed — search results are never affected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.schemas.search_query import SearchQueryCreate

if TYPE_CHECKING:
    from airweave.api.context import ApiContext


async def persist_v2_search_query(
    db: AsyncSession,
    ctx: ApiContext,
    *,
    collection_id: UUID,
    query_text: str,
    retrieval_strategy: str,
    is_streaming: bool,
    limit: int,
    offset: int,
    duration_ms: int,
    results_count: int,
    filter_groups: Optional[list[dict]] = None,
    expand_query: bool = False,
    interpret_filters: bool = False,
    rerank: bool = False,
    generate_answer: bool = False,
) -> None:
    """Persist a V2 search query record. Never raises."""
    try:
        api_key_id: Optional[str] = None
        if ctx.is_api_key_auth and ctx.auth_metadata:
            api_key_id = ctx.auth_metadata.get("api_key_id")

        filter_dict: Optional[dict] = None
        if filter_groups:
            filter_dict = {"groups": filter_groups}

        record = SearchQueryCreate(
            collection_id=collection_id,
            user_id=ctx.user.id if ctx.user else None,
            api_key_id=UUID(api_key_id) if api_key_id else None,
            query_text=query_text,
            query_length=len(query_text),
            is_streaming=is_streaming,
            retrieval_strategy=retrieval_strategy,
            limit=limit,
            offset=offset,
            temporal_relevance=0.0,
            filter=filter_dict,
            duration_ms=duration_ms,
            results_count=results_count,
            expand_query=expand_query,
            interpret_filters=interpret_filters,
            rerank=rerank,
            generate_answer=generate_answer,
        )

        await crud.search_query.create(db=db, obj_in=record, ctx=ctx)

        ctx.logger.debug(
            f"V2 search query persisted query={query_text[:50]!r} "
            f"strategy={retrieval_strategy} results={results_count}"
        )
    except Exception as e:
        ctx.logger.warning(
            f"Failed to persist V2 search query: {e}. "
            "Search completed successfully but the search_queries row was not saved."
        )
