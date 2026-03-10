"""Agent loop state schema."""

from pydantic import BaseModel, Field

from .search_result import AgenticSearchResult


class AgenticSearchState(BaseModel):
    """Mutable state for the agentic search conversation loop."""

    messages: list[dict] = Field(default_factory=list)
    results: dict[str, AgenticSearchResult] = Field(default_factory=dict)
    results_by_tool_call_id: dict[str, list[AgenticSearchResult]] = Field(default_factory=dict)
    reads_by_tool_call_id: dict[str, list[AgenticSearchResult]] = Field(default_factory=dict)
    result_entity_ids: set[str] = Field(default_factory=set)
    iteration: int = 0
    should_finish: bool = False
    return_warned: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def add_to_results(self, entity_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
        """Add entity IDs to the result set.

        Returns:
            Tuple of (newly added, already in results, not found in search results).
        """
        newly_added: list[str] = []
        already_added: list[str] = []
        not_found: list[str] = []
        for eid in entity_ids:
            if eid not in self.results:
                not_found.append(eid)
            elif eid in self.result_entity_ids:
                already_added.append(eid)
            else:
                self.result_entity_ids.add(eid)
                newly_added.append(eid)
        return newly_added, already_added, not_found
