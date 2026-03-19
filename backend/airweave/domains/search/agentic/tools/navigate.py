"""Navigation tools — traverse entity hierarchy without search queries.

get_children/get_siblings return summaries (like search).
get_parent returns full content (like read).
"""

from __future__ import annotations

from typing import Any

from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.agentic.exceptions import ToolValidationError
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import (
    NavigateToolResult,
    ReadToolResult,
    RenderedResult,
)
from airweave.domains.search.types.filters import (
    FilterableField,
    FilterCondition,
    FilterGroup,
    FilterOperator,
)

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
                "entity_id": {
                    "type": "string",
                    "description": "Parent entity ID.",
                },
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
            "Find entities with the same parent as the given entity. "
            "The entity must be in your search results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Entity ID (must be in search results).",
                },
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
            "Get the parent entity of a given entity. "
            "The entity must be in your search results. "
            "Returns the full content of the parent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Entity ID (must be in search results).",
                },
            },
            "required": ["entity_id"],
        },
    },
}


class GetChildrenTool:
    """Find all direct children of an entity."""

    def __init__(self, vector_db: VectorDBProtocol, collection_id: str) -> None:
        """Initialize with vector DB and collection ID."""
        self._vector_db = vector_db
        self._collection_id = collection_id

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> NavigateToolResult:
        """Fetch direct children using breadcrumb filter."""
        entity_id = arguments.get("entity_id")
        if not entity_id:
            raise ToolValidationError("entity_id is required")
        limit = min(arguments.get("limit", 50), 200)

        filter_groups = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.BREADCRUMBS_ENTITY_ID,
                        operator=FilterOperator.EQUALS,
                        value=entity_id,
                    )
                ]
            )
        ]

        raw_results = await self._vector_db.filter_search(
            filter_groups=filter_groups,
            collection_id=self._collection_id,
            limit=limit,
        )

        # Post-filter to direct children (last breadcrumb is the parent)
        children = [
            r for r in raw_results if r.breadcrumbs and r.breadcrumbs[-1].entity_id == entity_id
        ]

        # Add to state
        for r in children:
            if r.entity_id not in state.results:
                state.results[r.entity_id] = r
        if tool_call_id:
            state.results_by_tool_call_id[tool_call_id] = children

        parent_entity = state.results.get(entity_id)
        parent_name = parent_entity.name if parent_entity else entity_id
        parent_source = parent_entity.airweave_system_metadata.source_name if parent_entity else ""

        summaries = [
            RenderedResult(entity_id=r.entity_id, text=r.to_snippet_summary_md()) for r in children
        ]

        label = (
            f'children of "{parent_name}" ({parent_source})'
            if parent_source
            else f'children of "{parent_name}"'
        )
        return NavigateToolResult(
            summaries=summaries,
            context_label=label,
        )


class GetSiblingsTool:
    """Find siblings (entities with the same parent)."""

    def __init__(self, vector_db: VectorDBProtocol, collection_id: str) -> None:
        """Initialize with vector DB and collection ID."""
        self._vector_db = vector_db
        self._collection_id = collection_id

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> NavigateToolResult:
        """Fetch siblings by finding parent from breadcrumbs, then its children."""
        entity_id = arguments.get("entity_id")
        if not entity_id:
            raise ToolValidationError("entity_id is required")

        entity = state.results.get(entity_id)
        if not entity:
            raise ToolValidationError(
                f"Entity '{entity_id}' not found in search results. "
                "Search for it first, then call get_siblings."
            )

        if not entity.breadcrumbs:
            raise ToolValidationError(
                f"Entity '{entity_id}' has no breadcrumbs (root entity). Cannot find siblings."
            )

        parent = entity.breadcrumbs[-1]
        limit = min(arguments.get("limit", 50), 200)

        filter_groups = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.BREADCRUMBS_ENTITY_ID,
                        operator=FilterOperator.EQUALS,
                        value=parent.entity_id,
                    )
                ]
            )
        ]

        raw_results = await self._vector_db.filter_search(
            filter_groups=filter_groups,
            collection_id=self._collection_id,
            limit=limit,
        )

        siblings = [
            r
            for r in raw_results
            if r.breadcrumbs and r.breadcrumbs[-1].entity_id == parent.entity_id
        ]

        for r in siblings:
            if r.entity_id not in state.results:
                state.results[r.entity_id] = r
        if tool_call_id:
            state.results_by_tool_call_id[tool_call_id] = siblings

        summaries = [
            RenderedResult(entity_id=r.entity_id, text=r.to_snippet_summary_md()) for r in siblings
        ]

        parent_source = (
            entity.airweave_system_metadata.source_name if entity.airweave_system_metadata else ""
        )
        label = (
            f'siblings of "{parent.name}" ({parent_source})'
            if parent_source
            else f'siblings of "{parent.name}"'
        )
        return NavigateToolResult(
            summaries=summaries,
            context_label=label,
        )


class GetParentTool:
    """Fetch the parent entity — returns full content (like a read)."""

    def __init__(self, vector_db: VectorDBProtocol, collection_id: str) -> None:
        """Initialize with vector DB and collection ID."""
        self._vector_db = vector_db
        self._collection_id = collection_id

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> ReadToolResult:
        """Fetch parent entity by looking up breadcrumbs. Returns full content."""
        entity_id = arguments.get("entity_id")
        if not entity_id:
            raise ToolValidationError("entity_id is required")

        entity = state.results.get(entity_id)
        if not entity:
            raise ToolValidationError(f"Entity '{entity_id}' not found in search results.")

        if not entity.breadcrumbs:
            raise ToolValidationError(f"Entity '{entity_id}' is a root entity — no parent.")

        parent_bc = entity.breadcrumbs[-1]

        entity_source = (
            entity.airweave_system_metadata.source_name if entity.airweave_system_metadata else ""
        )
        context_label = (
            f'parent of "{entity.name}" ({entity_source})'
            if entity_source
            else f'parent of "{entity.name}"'
        )

        # Check if parent already in state
        if parent_bc.entity_id in state.results:
            parent = state.results[parent_bc.entity_id]
            return ReadToolResult(
                entities=[RenderedResult(entity_id=parent.entity_id, text=parent.to_md())],
                not_found=[],
                context_label=context_label,
            )

        # Fetch from vector DB
        filter_groups = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.ENTITY_ID,
                        operator=FilterOperator.EQUALS,
                        value=parent_bc.entity_id,
                    )
                ]
            )
        ]

        results = await self._vector_db.filter_search(
            filter_groups=filter_groups,
            collection_id=self._collection_id,
            limit=1,
        )

        for r in results:
            state.results[r.entity_id] = r
        if tool_call_id:
            state.reads_by_tool_call_id[tool_call_id] = results

        if results:
            parent = results[0]
            return ReadToolResult(
                entities=[RenderedResult(entity_id=parent.entity_id, text=parent.to_md())],
                not_found=[],
                context_label=context_label,
            )

        return ReadToolResult(
            entities=[], not_found=[parent_bc.entity_id], context_label=context_label
        )
