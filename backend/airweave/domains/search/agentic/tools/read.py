"""Read tool — fetch full content of search results with surrounding chunks.

Returns full content (via to_md) — the context manager decides how many fit.
"""

from __future__ import annotations

from typing import Any

from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.agentic.exceptions import ToolValidationError
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import ReadToolResult, RenderedResult
from airweave.domains.search.types.filters import (
    FilterableField,
    FilterCondition,
    FilterGroup,
    FilterOperator,
)
from airweave.domains.search.types.results import SearchResult

READ_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read",
        "description": (
            "Read the full content of search results by entity ID. "
            "Returns the complete text content with surrounding chunks for context. "
            "Use this after searching to examine results in detail before collecting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs to read (from search results).",
                },
            },
            "required": ["entity_ids"],
        },
    },
}


class ReadTool:
    """Fetches full content for entities, including surrounding chunks for context."""

    def __init__(
        self,
        vector_db: VectorDBProtocol,
        collection_id: str,
        surrounding_chunks: int = 2,
    ) -> None:
        """Initialize with vector DB, collection ID, and chunk window size."""
        self._vector_db = vector_db
        self._collection_id = collection_id
        self._surrounding_chunks = surrounding_chunks

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> ReadToolResult:
        """Fetch full content for requested entities."""
        entity_ids = arguments.get("entity_ids", [])
        if not entity_ids:
            raise ToolValidationError("entity_ids is required and cannot be empty")

        entities: list[RenderedResult] = []
        not_found: list[str] = []
        all_read_results: list[SearchResult] = []

        # Group requested IDs by original_entity_id for efficient chunk fetching
        groups: dict[str, list[SearchResult]] = {}
        for eid in entity_ids:
            result = state.results.get(eid)
            if not result:
                not_found.append(eid)
                continue
            orig_id = result.airweave_system_metadata.original_entity_id
            groups.setdefault(orig_id, []).append(result)

        for orig_id, group_results in groups.items():
            chunks = await self._fetch_chunks(orig_id, group_results, state)
            all_read_results.extend(chunks)

            # Side-load fetched chunks into state
            for chunk in chunks:
                if chunk.entity_id not in state.results:
                    state.results[chunk.entity_id] = chunk

            # Render as full content
            text = self._render_chunks(group_results[0].name, chunks, group_results)
            entities.append(RenderedResult(entity_id=group_results[0].entity_id, text=text))

        if tool_call_id:
            state.reads_by_tool_call_id[tool_call_id] = all_read_results

        return ReadToolResult(entities=entities, not_found=not_found)

    def _render_chunks(
        self,
        name: str,
        chunks: list[SearchResult],
        matched_results: list[SearchResult],
    ) -> str:
        """Render chunks as markdown. Single chunk uses to_md(), multi-chunk shows chunk labels."""
        if len(chunks) == 1:
            return chunks[0].to_md()

        matched_indices = {r.airweave_system_metadata.chunk_index for r in matched_results}
        parts = [f"### {name}\n"]
        for chunk in chunks:
            idx = chunk.airweave_system_metadata.chunk_index
            marker = " <- search match" if idx in matched_indices else ""
            parts.append(f"**Chunk {idx}{marker}:**")
            parts.append("```")
            parts.append(chunk.textual_representation)
            parts.append("```\n")
        return "\n".join(parts)

    async def _fetch_chunks(
        self,
        original_entity_id: str,
        group_results: list[SearchResult],
        state: AgentState,
    ) -> list[SearchResult]:
        """Fetch surrounding chunks for a group of results sharing an original_entity_id."""
        chunk_indices = [r.airweave_system_metadata.chunk_index for r in group_results]
        min_chunk = min(chunk_indices) - self._surrounding_chunks
        max_chunk = max(chunk_indices) + self._surrounding_chunks

        filter_groups = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.ORIGINAL_ENTITY_ID,
                        operator=FilterOperator.EQUALS,
                        value=original_entity_id,
                    ),
                    FilterCondition(
                        field=FilterableField.CHUNK_INDEX,
                        operator=FilterOperator.GREATER_THAN_OR_EQUAL,
                        value=max(0, min_chunk),
                    ),
                    FilterCondition(
                        field=FilterableField.CHUNK_INDEX,
                        operator=FilterOperator.LESS_THAN_OR_EQUAL,
                        value=max_chunk,
                    ),
                ]
            )
        ]

        try:
            results = await self._vector_db.filter_search(
                filter_groups=filter_groups,
                collection_id=self._collection_id,
                limit=max(max_chunk - min_chunk + 1, 10),
            )
        except Exception:
            results = list(group_results)

        results.sort(key=lambda r: r.airweave_system_metadata.chunk_index)
        return results
