"""Builder for AgenticSearchState."""

from airweave.search.agentic_search.schemas import (
    AgenticSearchCollectionMetadata,
    AgenticSearchCurrentIteration,
    AgenticSearchRequest,
    AgenticSearchState,
)


class AgenticSearchStateBuilder:
    """Builds AgenticSearchState for the agent."""

    def build_initial(
        self,
        request: AgenticSearchRequest,
        collection_metadata: AgenticSearchCollectionMetadata,
    ) -> AgenticSearchState:
        """Create the initial state for a agentic search.

        Args:
            collection_metadata: The collection metadata.
            request: The agentic search request.

        Returns:
            Initial AgenticSearchState ready for the first iteration.
        """
        return AgenticSearchState(
            user_query=request.query,
            user_filter=request.filter,
            mode=request.mode,
            collection_metadata=collection_metadata,
            iteration_number=0,
            current_iteration=AgenticSearchCurrentIteration(
                plan=None,
                query_embeddings=None,
                compiled_query=None,
                search_results=None,
                evaluation=None,
            ),
            history=None,
        )
