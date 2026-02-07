"""Builder for SpotlightState."""

from airweave.search.spotlight.schemas import (
    SpotlightCollectionMetadata,
    SpotlightCurrentIteration,
    SpotlightRequest,
    SpotlightState,
)


class SpotlightStateBuilder:
    """Builds SpotlightState for the agent."""

    def build_initial(
        self,
        request: SpotlightRequest,
        collection_metadata: SpotlightCollectionMetadata,
    ) -> SpotlightState:
        """Create the initial state for a spotlight search.

        Args:
            collection_metadata: The collection metadata.
            request: The spotlight search request.

        Returns:
            Initial SpotlightState ready for the first iteration.
        """
        return SpotlightState(
            user_query=request.query,
            user_filter=request.filter,
            mode=request.mode,
            collection_metadata=collection_metadata,
            iteration_number=0,
            current_iteration=SpotlightCurrentIteration(
                plan=None,
                query_embeddings=None,
                compiled_query=None,
                search_results=None,
                evaluation=None,
            ),
            history=None,
        )
