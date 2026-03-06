"""Agent loop state schema."""

from pydantic import BaseModel, Field

from .search_result import AgenticSearchResult


class AgenticSearchState(BaseModel):
    """Mutable state for the agentic search conversation loop."""

    messages: list[dict] = Field(default_factory=list)
    results: dict[str, AgenticSearchResult] = Field(default_factory=dict)
    results_by_tool_call_id: dict[str, list[AgenticSearchResult]] = Field(default_factory=dict)
    marked_entity_ids: set[str] = Field(default_factory=set)
    iteration: int = 0

    model_config = {"arbitrary_types_allowed": True}

    def mark_as_relevant(self, entity_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
        """Mark entity IDs as relevant.

        Returns:
            Tuple of (newly marked, already marked, not found in results).
        """
        newly_marked: list[str] = []
        already_marked: list[str] = []
        not_found: list[str] = []
        for eid in entity_ids:
            if eid not in self.results:
                not_found.append(eid)
            elif eid in self.marked_entity_ids:
                already_marked.append(eid)
            else:
                self.marked_entity_ids.add(eid)
                newly_marked.append(eid)
        return newly_marked, already_marked, not_found
