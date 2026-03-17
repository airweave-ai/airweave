"""Collect tools — add or remove entities from the result set."""

from __future__ import annotations

from typing import Any

from airweave.domains.search.agentic.exceptions import ToolValidationError
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import CollectToolResult

ADD_TO_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_to_results",
        "description": (
            "Add entities to the result set you're building for the user. "
            "Include everything the user would want to see. "
            "The cost of including a borderline result is low (the user scrolls past it). "
            "The cost of missing a matching result is high (the user never finds it). "
            "You can call this multiple times; results accumulate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs to add to the result set.",
                },
            },
            "required": ["entity_ids"],
        },
    },
}

REMOVE_FROM_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "remove_from_results",
        "description": (
            "Remove entities from your result set. Use this when you realize "
            "collected results don't actually match the query. "
            "Pass 'all' as the only entity ID to clear everything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Entity IDs to remove from the result set. "
                        "Pass ['all'] to clear all results."
                    ),
                },
            },
            "required": ["entity_ids"],
        },
    },
}


class AddToResultsTool:
    """Add entities to the collected result set."""

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> CollectToolResult:
        """Add entity IDs to the result set."""
        entity_ids = arguments.get("entity_ids", [])
        if not entity_ids:
            raise ToolValidationError("entity_ids is required and cannot be empty")

        newly_added, already, not_found = state.add_to_collected(entity_ids)

        return CollectToolResult(
            added=newly_added,
            already_collected=already,
            not_found=not_found,
            total_collected=len(state.collected_ids),
        )


class RemoveFromResultsTool:
    """Remove entities from the collected result set."""

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> CollectToolResult:
        """Remove entity IDs from the result set."""
        entity_ids = arguments.get("entity_ids", [])
        if not entity_ids:
            raise ToolValidationError("entity_ids is required and cannot be empty")

        if entity_ids == ["all"]:
            state.collected_ids.clear()
            return CollectToolResult(
                removed=["all"],
                total_collected=0,
            )

        removed, not_in = state.remove_from_collected(entity_ids)

        return CollectToolResult(
            removed=removed,
            not_found=not_in,
            total_collected=len(state.collected_ids),
        )
