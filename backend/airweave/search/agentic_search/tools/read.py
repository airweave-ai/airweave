"""Read tool: definition and handler.

Allows the agent to read the full content of search results by entity ID,
with surrounding chunks for context on chunked documents. Replaces the old
read_previous_results tool with chunk-aware reads via the vector database.
"""

from typing import Any

from airweave.search.agentic_search.config import CHARS_PER_TOKEN, config as agentic_config
from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools.search import (
    _estimate_available_tokens,
    execute_search,
)

# ── Tool definition (sent to the LLM) ────────────────────────────────

READ_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read",
        "description": (
            "Read the full content of search results by entity ID. "
            "Returns the complete text content with surrounding chunks for context. "
            "Use this after searching to examine results in detail before marking."
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


# ── Handler ───────────────────────────────────────────────────────────


async def handle_read(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Read full content of search results with surrounding chunks.

    For each requested entity_id:
    1. Look up in state.results to get original_entity_id and chunk_index
    2. Fetch surrounding chunks from the vector database
    3. Format as full content with chunk labels
    4. Append inline triage nudge
    """
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])
    if not entity_ids:
        return "No entity IDs provided."

    surrounding = agentic_config.READ_SURROUNDING_CHUNKS
    available_tokens = _estimate_available_tokens(state.messages, context_window_tokens)
    max_chars = available_tokens * CHARS_PER_TOKEN

    # Group requested IDs by original_entity_id
    groups: dict[str, _ReadGroup] = {}
    not_found: list[str] = []

    for eid in entity_ids:
        result = state.results.get(eid)
        if result is None:
            not_found.append(eid)
            continue
        meta = result.airweave_system_metadata
        orig_id = meta.original_entity_id
        if orig_id not in groups:
            groups[orig_id] = _ReadGroup(
                original_entity_id=orig_id,
                name=result.name,
                chunk_indices=[meta.chunk_index],
                matched_entity_ids=[eid],
            )
        else:
            groups[orig_id].chunk_indices.append(meta.chunk_index)
            if eid not in groups[orig_id].matched_entity_ids:
                groups[orig_id].matched_entity_ids.append(eid)

    if not groups and not_found:
        return f"**Not found in previous search results:** {', '.join(not_found)}"

    parts: list[str] = []
    all_read_results: list[AgenticSearchResult] = []
    chars_used = 0
    entities_read = 0

    for orig_id, group in groups.items():
        min_chunk = min(group.chunk_indices)
        max_chunk = max(group.chunk_indices)
        range_min = max(0, min_chunk - surrounding)
        range_max = max_chunk + surrounding
        range_size = range_max - range_min + 1

        # Try to fetch surrounding chunks from the vector database
        fetched_chunks = await _fetch_chunks(
            original_entity_id=orig_id,
            entity_name=group.name,
            chunk_min=range_min,
            chunk_max=range_max,
            range_size=range_size,
            services=services,
            collection_id=collection_id,
            user_filter=user_filter,
        )

        if not fetched_chunks:
            # Fallback: use the result(s) we already have in state
            for eid in group.matched_entity_ids:
                r = state.results.get(eid)
                if r:
                    fetched_chunks.append(r)

        # Sort by chunk_index
        fetched_chunks.sort(key=lambda r: r.airweave_system_metadata.chunk_index)

        # Store all fetched chunks in state (so they're available for marking)
        for chunk in fetched_chunks:
            if chunk.entity_id not in state.results:
                state.results[chunk.entity_id] = chunk
            all_read_results.append(chunk)

        # Format this entity's chunks
        matched_indices = set(group.chunk_indices)
        entity_part = _format_entity_chunks(
            group=group,
            chunks=fetched_chunks,
            matched_indices=matched_indices,
        )

        if chars_used + len(entity_part) > max_chars and parts:
            parts.append(f"\n\n*(Truncated — token budget reached. "
                         f"{len(groups) - entities_read} entities not shown.)*")
            break

        parts.append(entity_part)
        chars_used += len(entity_part)
        entities_read += 1

    # Store reads for context management
    state.reads_by_tool_call_id[tc.id] = all_read_results

    # Build output
    header = f"**Reading {entities_read} entities:**\n"

    # Not found section
    not_found_section = ""
    if not_found:
        not_found_section = f"\n\n**Not found in previous search results:** {', '.join(not_found)}"

    # All entity IDs that were read (for triage nudge)
    all_read_ids = []
    for group in groups.values():
        all_read_ids.extend(group.matched_entity_ids)

    # Triage nudge
    id_list = ", ".join(f"`{eid}`" for eid in all_read_ids[:20])
    triage_nudge = (
        f"\n\n**Entities read:** [{id_list}]\n"
        f"Mark relevant results now (`mark_as_relevant`) "
        f"— their content will be summarized after your next search."
    )

    return header + "\n".join(parts) + not_found_section + triage_nudge


# ── Internal helpers ──────────────────────────────────────────────────


class _ReadGroup:
    """Groups requested entity IDs by their original_entity_id."""

    __slots__ = ("original_entity_id", "name", "chunk_indices", "matched_entity_ids")

    def __init__(
        self,
        original_entity_id: str,
        name: str,
        chunk_indices: list[int],
        matched_entity_ids: list[str],
    ) -> None:
        self.original_entity_id = original_entity_id
        self.name = name
        self.chunk_indices = chunk_indices
        self.matched_entity_ids = matched_entity_ids


async def _fetch_chunks(
    original_entity_id: str,
    entity_name: str,
    chunk_min: int,
    chunk_max: int,
    range_size: int,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
) -> list[AgenticSearchResult]:
    """Fetch chunks from the vector database for a specific original_entity_id."""
    try:
        # Build filter: original_entity_id equals <id> AND chunk_index in range
        chunk_filters = [
            {
                "conditions": [
                    {
                        "field": "airweave_system_metadata.original_entity_id",
                        "operator": "equals",
                        "value": original_entity_id,
                    },
                    {
                        "field": "airweave_system_metadata.chunk_index",
                        "operator": "greater_than_or_equal",
                        "value": chunk_min,
                    },
                    {
                        "field": "airweave_system_metadata.chunk_index",
                        "operator": "less_than_or_equal",
                        "value": chunk_max,
                    },
                ]
            }
        ]

        results = await execute_search(
            arguments={
                "query": {"primary": entity_name},
                "retrieval_strategy": "semantic",
                "filter_groups": chunk_filters,
                "limit": max(range_size, 10),
                "offset": 0,
            },
            user_filter=user_filter,
            dense_embedder=services.dense_embedder,
            sparse_embedder=services.sparse_embedder,
            vector_db=services.vector_db,
            collection_id=collection_id,
        )
        return results
    except Exception:
        return []


def _format_entity_chunks(
    group: _ReadGroup,
    chunks: list[AgenticSearchResult],
    matched_indices: set[int],
) -> str:
    """Format chunks for a single entity with chunk labels."""
    if not chunks:
        return f"\n---\n\n### {group.name} (original_entity_id: {group.original_entity_id})\n*No chunks retrieved.*"

    # Single-chunk entity (chunk_index 0 and only one chunk)
    if len(chunks) == 1 and chunks[0].airweave_system_metadata.chunk_index == 0:
        return f"\n---\n\n{chunks[0].to_md()}"

    # Multi-chunk entity
    all_indices = [c.airweave_system_metadata.chunk_index for c in chunks]
    min_idx = min(all_indices)
    max_idx = max(all_indices)

    matched_str = ", ".join(str(i) for i in sorted(matched_indices))
    header = (
        f"\n---\n\n### {group.name} (original_entity_id: {group.original_entity_id})\n"
        f"Showing chunks {min_idx}-{max_idx} (centered on matched chunk(s) {matched_str})\n"
    )

    chunk_parts: list[str] = []
    for chunk in chunks:
        idx = chunk.airweave_system_metadata.chunk_index
        label = f"**Chunk {idx}"
        if idx in matched_indices:
            label += " <- search match"
        label += ":**"

        chunk_parts.append(f"\n{label}\n```\n{chunk.textual_representation}\n```")

    return header + "\n".join(chunk_parts)
