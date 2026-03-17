"""Mutable state for the agentic search agent.

Tracks all entities discovered during the search, which ones are collected
into the final result set, and tool call lineage for context management.
"""

from __future__ import annotations

from airweave.domains.search.types.results import SearchResult


class AgentState:
    """Mutable state for the agentic search agent.

    Fields:
        results: All entities discovered (keyed by entity_id). The "seen" pool.
        results_by_tool_call_id: Which tool call found which results (for context management).
        reads_by_tool_call_id: Which tool call read which entities (for context management).
        collected_ids: Entity IDs in the final result set (subset of results keys).
        should_finish: Signal to stop the agent loop.
        return_warned: Soft-gate flag — warned once before allowing finish.
    """

    def __init__(self) -> None:
        """Initialize empty state."""
        self.results: dict[str, SearchResult] = {}
        self.results_by_tool_call_id: dict[str, list[SearchResult]] = {}
        self.reads_by_tool_call_id: dict[str, list[SearchResult]] = {}
        self.collected_ids: set[str] = set()
        self.should_finish: bool = False
        self.return_warned: bool = False

    def add_to_collected(self, entity_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
        """Add entity IDs to the collected result set.

        Returns:
            (newly_added, already_collected, not_found) — three lists of entity IDs.
        """
        newly_added: list[str] = []
        already_collected: list[str] = []
        not_found: list[str] = []
        for eid in entity_ids:
            if eid not in self.results:
                not_found.append(eid)
            elif eid in self.collected_ids:
                already_collected.append(eid)
            else:
                self.collected_ids.add(eid)
                newly_added.append(eid)
        return newly_added, already_collected, not_found

    def remove_from_collected(self, entity_ids: list[str]) -> tuple[list[str], list[str]]:
        """Remove entity IDs from the collected result set.

        Returns:
            (removed, not_in_collected) — two lists of entity IDs.
        """
        removed: list[str] = []
        not_in_collected: list[str] = []
        for eid in entity_ids:
            if eid in self.collected_ids:
                self.collected_ids.discard(eid)
                removed.append(eid)
            else:
                not_in_collected.append(eid)
        return removed, not_in_collected
