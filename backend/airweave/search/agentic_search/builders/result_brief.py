"""Builder for deterministic result briefs.

Extracts compact metadata from search results for history storage.
No LLM involvement — purely deterministic.
"""

from airweave.search.agentic_search.schemas.search_result import (
    AgenticSearchResults,
    ResultBrief,
    ResultBriefEntry,
)


class AgenticSearchResultBriefBuilder:
    """Builds a deterministic ResultBrief from search results.

    Extracts metadata from the top N results including breadcrumb info
    so the planner can build exploration filters.
    """

    @staticmethod
    def build(
        search_results: AgenticSearchResults,
    ) -> ResultBrief:
        """Build a ResultBrief from search results.

        Extracts metadata from ALL results without any LLM involvement.
        Includes parent breadcrumb info (name, entity_type, entity_id) so the
        planner can filter by breadcrumb fields.

        The result brief entries are compact (~20 tokens each) so including all
        results is fine — the history token budget handles truncation naturally.

        Args:
            search_results: The search results to summarize.

        Returns:
            A ResultBrief with metadata from all results.
        """
        entries: list[ResultBriefEntry] = []
        for result in search_results.results:
            breadcrumb_path = (
                " > ".join(bc.name for bc in result.breadcrumbs) if result.breadcrumbs else "(root)"
            )

            # Extract parent (deepest) breadcrumb info for filter building
            parent_bc = result.breadcrumbs[-1] if result.breadcrumbs else None

            entries.append(
                ResultBriefEntry(
                    name=result.name,
                    source_name=result.airweave_system_metadata.source_name,
                    entity_type=result.airweave_system_metadata.entity_type,
                    original_entity_id=result.airweave_system_metadata.original_entity_id,
                    chunk_index=result.airweave_system_metadata.chunk_index,
                    relevance_score=result.relevance_score,
                    breadcrumb_path=breadcrumb_path,
                    parent_breadcrumb_name=parent_bc.name if parent_bc else None,
                    parent_breadcrumb_entity_type=parent_bc.entity_type if parent_bc else None,
                    parent_breadcrumb_entity_id=parent_bc.entity_id if parent_bc else None,
                )
            )
        return ResultBrief(total_count=len(search_results), entries=entries)
