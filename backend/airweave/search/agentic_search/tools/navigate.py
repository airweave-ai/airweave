"""Navigation tools: get_children, get_siblings, get_parent.

Structural navigation tools that make hierarchy traversal a first-class
operation. All use filter_search() (no embeddings) for fast, cheap queries.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools.search import (
    _estimate_available_tokens,
    format_search_summaries,
)

# ── Tool definitions (sent to the LLM) ────────────────────────────────

GET_CHILDREN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_children",
        "description": (
            "Find all entities inside a container (e.g., all messages in a channel, "
            "all pages in a folder). Takes any entity_id — it doesn't need to be in "
            "your results. Returns compact summaries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Parent entity ID."},
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50, max 200).",
                    "default": 50,
                },
            },
            "required": ["entity_id"],
        },
    },
}

GET_SIBLINGS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_siblings",
        "description": (
            "Find all entities sharing the same parent as a given entity. "
            "The entity must be in your results. Use this for group completion — "
            "when you find one message in a thread, get its siblings to find "
            "the full thread. Returns compact summaries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID (must be in your results)."},
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50, max 200).",
                    "default": 50,
                },
            },
            "required": ["entity_id"],
        },
    },
}

GET_PARENT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_parent",
        "description": (
            "Find the parent entity of a given entity. The entity must be in "
            "your results. Returns full content. Use this to understand context — "
            "what channel/folder/project something belongs to."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID (must be in your results)."},
            },
            "required": ["entity_id"],
        },
    },
}


# ── Shared helpers ─────────────────────────────────────────────────────


def _build_breadcrumb_filter(parent_entity_id: str) -> list[dict]:
    """Build filter_groups to find entities whose breadcrumbs contain parent_entity_id."""
    return [
        {
            "conditions": [
                {
                    "field": "breadcrumbs.entity_id",
                    "operator": "equals",
                    "value": parent_entity_id,
                }
            ]
        }
    ]


def _build_entity_id_filter(entity_id: str) -> list[dict]:
    """Build filter_groups to find an entity by its entity_id."""
    return [
        {
            "conditions": [
                {
                    "field": "entity_id",
                    "operator": "equals",
                    "value": entity_id,
                }
            ]
        }
    ]


def _merge_filters(navigation_filters: list[dict], user_filter: list) -> list[dict]:
    """Merge navigation filters with user filters.

    Navigation filters have one group with conditions. User filters are
    additional groups. We AND the user filter conditions into each
    navigation filter group.
    """
    if not user_filter:
        return navigation_filters

    # Add user filter conditions to each navigation filter group
    merged = []
    for nav_group in navigation_filters:
        merged_group = dict(nav_group)
        merged_conditions = list(nav_group.get("conditions", []))
        for uf_group in user_filter:
            merged_conditions.extend(uf_group.get("conditions", []))
        merged_group["conditions"] = merged_conditions
        merged.append(merged_group)
    return merged


def _filter_direct_children(
    results: list[AgenticSearchResult], parent_entity_id: str
) -> list[AgenticSearchResult]:
    """Post-filter to keep only results whose last breadcrumb matches parent_entity_id.

    Without ranking, all-descendants would return arbitrary results from mixed
    hierarchy levels. This ensures consistent single-level results.
    """
    direct = []
    for r in results:
        if r.breadcrumbs and r.breadcrumbs[-1].entity_id == parent_entity_id:
            direct.append(r)
    return direct


def _get_parent_info(result: AgenticSearchResult) -> tuple[str, str] | None:
    """Extract (parent_entity_id, parent_name) from result's last breadcrumb."""
    if not result.breadcrumbs:
        return None
    parent = result.breadcrumbs[-1]
    return parent.entity_id, parent.name


# ── Handlers ───────────────────────────────────────────────────────────


async def handle_get_children(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Find all direct children of a container entity."""
    entity_id: str = tc.arguments.get("entity_id", "")
    limit: int = min(tc.arguments.get("limit", 50), 200)

    if not entity_id:
        return "No entity_id provided."

    # Build filter and query
    filters = _merge_filters(_build_breadcrumb_filter(entity_id), user_filter)
    try:
        all_results = await services.vector_db.filter_search(
            filter_groups=filters,
            collection_id=collection_id,
            limit=limit,
        )
    except Exception as e:
        return f"Navigation query failed: {e}"

    # Post-filter to direct children only
    results = _filter_direct_children(all_results, entity_id)

    # Store in state
    for r in results:
        if r.entity_id not in state.results:
            state.results[r.entity_id] = r
    state.results_by_tool_call_id[tc.id] = results

    # Try to get entity name from state or results
    entity_name = entity_id
    if entity_id in state.results:
        entity_name = state.results[entity_id].name
    else:
        # Check if any result has this as a breadcrumb
        for r in results:
            if r.breadcrumbs and r.breadcrumbs[-1].entity_id == entity_id:
                entity_name = r.breadcrumbs[-1].name
                break

    # Format
    available_tokens = _estimate_available_tokens(state.messages, context_window_tokens)
    header = f"**{len(results)} children** of {entity_name} [{entity_id}]:\n\n"

    if not results:
        return header + "No children found."

    summaries = format_search_summaries(results, available_tokens)
    return header + summaries


async def handle_get_siblings(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Find all entities sharing the same parent as a given entity."""
    entity_id: str = tc.arguments.get("entity_id", "")
    limit: int = min(tc.arguments.get("limit", 50), 200)

    if not entity_id:
        return "No entity_id provided."

    # Look up entity in state
    result = state.results.get(entity_id)
    if result is None:
        return f"Entity `{entity_id}` not found in your results. Use an entity ID from search results."

    # Extract parent
    parent_info = _get_parent_info(result)
    if parent_info is None:
        return f"Entity `{entity_id}` has no breadcrumbs — cannot determine parent."

    parent_id, parent_name = parent_info

    # Build filter and query
    filters = _merge_filters(_build_breadcrumb_filter(parent_id), user_filter)
    try:
        all_results = await services.vector_db.filter_search(
            filter_groups=filters,
            collection_id=collection_id,
            limit=limit,
        )
    except Exception as e:
        return f"Navigation query failed: {e}"

    # Post-filter to true siblings (same depth)
    results = _filter_direct_children(all_results, parent_id)

    # Store in state
    for r in results:
        if r.entity_id not in state.results:
            state.results[r.entity_id] = r
    state.results_by_tool_call_id[tc.id] = results

    # Format
    available_tokens = _estimate_available_tokens(state.messages, context_window_tokens)
    header = f"**{len(results)} siblings** (shared parent: {parent_name} [{parent_id}]):\n\n"

    if not results:
        return header + "No siblings found."

    summaries = format_search_summaries(results, available_tokens)
    return header + summaries


async def handle_get_parent(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Find the parent entity of a given entity."""
    entity_id: str = tc.arguments.get("entity_id", "")

    if not entity_id:
        return "No entity_id provided."

    # Look up entity in state
    result = state.results.get(entity_id)
    if result is None:
        return f"Entity `{entity_id}` not found in your results. Use an entity ID from search results."

    # Extract parent
    parent_info = _get_parent_info(result)
    if parent_info is None:
        return f"Entity `{entity_id}` has no breadcrumbs — it is a root entity with no parent."

    parent_id, parent_name = parent_info

    # Check if parent already in state
    if parent_id in state.results:
        parent_result = state.results[parent_id]
        state.reads_by_tool_call_id[tc.id] = [parent_result]
        return f"**Parent:** {parent_name} [{parent_id}] (already in results)\n\n{parent_result.to_md()}"

    # Query for the parent entity
    filters = _merge_filters(_build_entity_id_filter(parent_id), user_filter)
    try:
        results = await services.vector_db.filter_search(
            filter_groups=filters,
            collection_id=collection_id,
            limit=5,
        )
    except Exception as e:
        return f"Navigation query failed: {e}"

    if not results:
        return f"**Parent:** {parent_name} [{parent_id}] — not found in collection."

    # Store in state
    for r in results:
        if r.entity_id not in state.results:
            state.results[r.entity_id] = r
    state.reads_by_tool_call_id[tc.id] = results

    # Format with full content (single entity)
    return f"**Parent:** {parent_name} [{parent_id}]\n\n{results[0].to_md()}"
