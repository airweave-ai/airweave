"""Unit tests for Retrieval operation."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from airweave.search.operations.retrieval import Retrieval
from airweave.search.state import SearchState
from airweave.schemas.search import RetrievalStrategy
from airweave.schemas.search_result import AirweaveSearchResult, SystemMetadataResult


@pytest.fixture
def mock_destination():
    """Create mock destination."""
    dest = AsyncMock()
    dest.search = AsyncMock()
    dest.__class__.__name__ = "MockDestination"
    return dest


@pytest.fixture
def mock_context(mock_destination):
    """Create mock SearchContext."""
    context = MagicMock()
    context.query = "test query"
    context.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
    context.emitter = AsyncMock()
    context.reranking = None
    return context


@pytest.fixture
def mock_api_context():
    """Create mock ApiContext."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    return ctx


class TestRetrieval:
    """Test Retrieval operation executes search."""

    def test_initialization(self, mock_destination):
        """Test Retrieval initialization."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        assert retrieval.destination == mock_destination
        assert retrieval.strategy == RetrievalStrategy.HYBRID
        assert retrieval.offset == 0
        assert retrieval.limit == 10

    def test_depends_on(self, mock_destination):
        """Test depends_on returns expected dependencies."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        deps = retrieval.depends_on()
        
        assert "QueryInterpretation" in deps
        assert "EmbedQuery" in deps
        assert "UserFilter" in deps

    @pytest.mark.asyncio
    async def test_execute_calls_destination_search(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute calls destination.search()."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        state.sparse_embeddings = [MagicMock()]
        
        # Mock search results
        mock_result = AirweaveSearchResult(
            id="test-1",
            score=0.95,
            entity_id="entity-1",
            name="Test",
            textual_representation="Content",
            system_metadata=SystemMetadataResult(entity_type="document")
        )
        mock_destination.search.return_value = [mock_result]
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        # Verify destination.search was called
        mock_destination.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_emits_vector_search_start(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute emits vector_search_start event."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.NEURAL,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        mock_destination.search.return_value = []
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        # Verify event emitted
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "vector_search_start" in event_names

    @pytest.mark.asyncio
    async def test_execute_emits_vector_search_done(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute emits vector_search_done event."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        state.sparse_embeddings = [MagicMock()]
        mock_destination.search.return_value = []
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        # Verify event emitted
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "vector_search_done" in event_names

    @pytest.mark.asyncio
    async def test_execute_writes_results_to_state(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute writes results to state."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        state.sparse_embeddings = [MagicMock()]
        
        mock_result = AirweaveSearchResult(
            id="test-1",
            score=0.95,
            entity_id="entity-1",
            name="Test",
            textual_representation="Content",
            system_metadata=SystemMetadataResult(entity_type="document")
        )
        mock_destination.search.return_value = [mock_result]
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        assert len(state.results) > 0

    def test_get_search_method_hybrid(self, mock_destination):
        """Test _get_search_method returns 'hybrid' for HYBRID strategy."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        method = retrieval._get_search_method()
        assert method == "hybrid"

    def test_get_search_method_neural(self, mock_destination):
        """Test _get_search_method returns 'neural' for NEURAL strategy."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.NEURAL,
            offset=0,
            limit=10
        )
        
        method = retrieval._get_search_method()
        assert method == "neural"

    def test_get_search_method_keyword(self, mock_destination):
        """Test _get_search_method returns 'keyword' for KEYWORD strategy."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.KEYWORD,
            offset=0,
            limit=10
        )
        
        method = retrieval._get_search_method()
        assert method == "keyword"

    def test_calculate_fetch_limit_no_reranking(self, mock_destination, mock_context):
        """Test fetch limit without reranking."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=10,
            limit=20
        )
        
        mock_context.reranking = None
        
        fetch_limit = retrieval._calculate_fetch_limit(has_reranking=False, include_offset=True)
        
        assert fetch_limit == 30  # 10 + 20

    def test_calculate_fetch_limit_with_reranking(self, mock_destination, mock_context):
        """Test fetch limit with reranking applies multiplier."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=10,
            limit=20
        )
        
        mock_context.reranking = MagicMock()
        
        fetch_limit = retrieval._calculate_fetch_limit(has_reranking=True, include_offset=True)
        
        # Should be (10 + 20) * 2.0 = 60
        assert fetch_limit == 60

    def test_results_to_dicts_converts_search_results(self, mock_destination):
        """Test _results_to_dicts converts AirweaveSearchResult to dicts."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        results = [
            AirweaveSearchResult(
                id="test-1",
                score=0.95,
                entity_id="entity-1",
                name="Test",
                textual_representation="Content",
                system_metadata=SystemMetadataResult(entity_type="document")
            )
        ]
        
        dicts = retrieval._results_to_dicts(results)
        
        assert len(dicts) == 1
        assert isinstance(dicts[0], dict)
        assert dicts[0]["entity_id"] == "entity-1"

    def test_deduplicate_results_keeps_highest_score(self, mock_destination):
        """Test deduplication keeps result with highest score."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        results = [
            {"id": "doc-1", "entity_id": "entity-1", "score": 0.8},
            {"id": "doc-1", "entity_id": "entity-1", "score": 0.9},  # Higher score
            {"id": "doc-2", "entity_id": "entity-2", "score": 0.7},
        ]
        
        deduped = retrieval._deduplicate_results(results)
        
        assert len(deduped) == 2
        # doc-1 should have score 0.9
        doc1 = [r for r in deduped if r["id"] == "doc-1"][0]
        assert doc1["score"] == 0.9

    def test_deduplicate_results_sorts_by_score(self, mock_destination):
        """Test deduplication sorts by score descending."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        results = [
            {"id": "doc-1", "entity_id": "entity-1", "score": 0.7},
            {"id": "doc-2", "entity_id": "entity-2", "score": 0.9},
            {"id": "doc-3", "entity_id": "entity-3", "score": 0.8},
        ]
        
        deduped = retrieval._deduplicate_results(results)
        
        # Should be sorted by score descending
        assert deduped[0]["score"] == 0.9
        assert deduped[1]["score"] == 0.8
        assert deduped[2]["score"] == 0.7

    def test_apply_pagination_with_offset(self, mock_destination):
        """Test pagination applies offset correctly."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=2,
            limit=2
        )
        
        results = [
            {"id": "1", "score": 0.9},
            {"id": "2", "score": 0.8},
            {"id": "3", "score": 0.7},
            {"id": "4", "score": 0.6},
            {"id": "5", "score": 0.5},
        ]
        
        paginated = retrieval._apply_pagination(results)
        
        # Should skip first 2, return next 2
        assert len(paginated) == 2
        assert paginated[0]["id"] == "3"
        assert paginated[1]["id"] == "4"

    def test_apply_pagination_with_limit(self, mock_destination):
        """Test pagination applies limit correctly."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=3
        )
        
        results = [{"id": str(i), "score": 1.0 - i*0.1} for i in range(10)]
        
        paginated = retrieval._apply_pagination(results)
        
        assert len(paginated) == 3

    @pytest.mark.asyncio
    async def test_execute_emits_no_results_event(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute emits vector_search_no_results when no results found."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        state.sparse_embeddings = [MagicMock()]
        mock_destination.search.return_value = []  # No results
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        # Verify no_results event emitted
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "vector_search_no_results" in event_names

    @pytest.mark.asyncio
    async def test_execute_reports_metrics(
        self, mock_destination, mock_context, mock_api_context
    ):
        """Test execute reports metrics to state."""
        retrieval = Retrieval(
            destination=mock_destination,
            strategy=RetrievalStrategy.HYBRID,
            offset=0,
            limit=10
        )
        
        state = SearchState()
        state.dense_embeddings = [[0.1] * 3072]
        state.sparse_embeddings = [MagicMock()]
        mock_destination.search.return_value = []
        
        await retrieval.execute(mock_context, state, mock_api_context)
        
        # Metrics should be recorded
        assert "Retrieval" in state.operation_metrics

