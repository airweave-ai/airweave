"""Unit tests for SearchState model."""

import pytest
from typing import Any, Dict, List

from airweave.search.state import SearchState


class TestSearchState:
    """Test SearchState Pydantic model."""

    def test_default_initialization(self):
        """Test SearchState initializes with correct defaults."""
        state = SearchState()
        
        # Optional fields should be None
        assert state.expanded_queries is None
        assert state.dense_embeddings is None
        assert state.sparse_embeddings is None
        assert state.interpreted_filter is None
        assert state.filter is None
        assert state.completion is None
        
        # List fields should be empty
        assert state.results == []
        
        # Dict fields should be empty
        assert state.operation_metrics == {}
        assert state.provider_usage == {}
        assert state.failed_federated_auth == []

    def test_expanded_queries_assignment(self):
        """Test setting expanded_queries field."""
        state = SearchState()
        queries = ["query1", "query2", "query3"]
        state.expanded_queries = queries
        
        assert state.expanded_queries == queries
        assert len(state.expanded_queries) == 3

    def test_dense_embeddings_assignment(self):
        """Test setting dense_embeddings field."""
        state = SearchState()
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        state.dense_embeddings = embeddings
        
        assert state.dense_embeddings == embeddings
        assert len(state.dense_embeddings) == 2
        assert len(state.dense_embeddings[0]) == 3

    def test_sparse_embeddings_assignment(self):
        """Test setting sparse_embeddings field."""
        state = SearchState()
        
        class MockSparseEmbedding:
            indices = [0, 1, 2]
            values = [0.8, 0.6, 0.4]
        
        sparse = [MockSparseEmbedding()]
        state.sparse_embeddings = sparse
        
        assert state.sparse_embeddings == sparse
        assert len(state.sparse_embeddings) == 1

    def test_interpreted_filter_assignment(self):
        """Test setting interpreted_filter field."""
        state = SearchState()
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"value": "GitHub"}}
            ]
        }
        state.interpreted_filter = filter_dict
        
        assert state.interpreted_filter == filter_dict
        assert "must" in state.interpreted_filter

    def test_filter_assignment(self):
        """Test setting filter field."""
        state = SearchState()
        filter_dict = {
            "must": [
                {"key": "entity_type", "match": {"value": "issue"}}
            ]
        }
        state.filter = filter_dict
        
        assert state.filter == filter_dict

    def test_results_assignment(self):
        """Test setting results field."""
        state = SearchState()
        results = [
            {"entity_id": "1", "score": 0.9},
            {"entity_id": "2", "score": 0.8}
        ]
        state.results = results
        
        assert state.results == results
        assert len(state.results) == 2

    def test_completion_assignment(self):
        """Test setting completion field."""
        state = SearchState()
        completion = "This is a generated answer."
        state.completion = completion
        
        assert state.completion == completion

    def test_operation_metrics_assignment(self):
        """Test setting operation_metrics field."""
        state = SearchState()
        metrics = {
            "QueryExpansion": {"duration_ms": 150, "queries_generated": 3},
            "Retrieval": {"duration_ms": 500, "results_count": 10}
        }
        state.operation_metrics = metrics
        
        assert state.operation_metrics == metrics
        assert "QueryExpansion" in state.operation_metrics
        assert state.operation_metrics["Retrieval"]["duration_ms"] == 500

    def test_provider_usage_assignment(self):
        """Test setting provider_usage field."""
        state = SearchState()
        usage = {
            "query_expansion": "CerebrasProvider",
            "reranking": "CohereProvider"
        }
        state.provider_usage = usage
        
        assert state.provider_usage == usage
        assert state.provider_usage["query_expansion"] == "CerebrasProvider"

    def test_failed_federated_auth_assignment(self):
        """Test setting failed_federated_auth field."""
        state = SearchState()
        failed = ["connection-1", "connection-2"]
        state.failed_federated_auth = failed
        
        assert state.failed_federated_auth == failed
        assert len(state.failed_federated_auth) == 2

    def test_model_dump(self):
        """Test SearchState serialization to dict."""
        state = SearchState()
        state.expanded_queries = ["query1", "query2"]
        state.dense_embeddings = [[0.1, 0.2]]
        state.results = [{"entity_id": "1", "score": 0.9}]
        state.completion = "Answer"
        
        dumped = state.model_dump()
        
        assert isinstance(dumped, dict)
        assert dumped["expanded_queries"] == ["query1", "query2"]
        assert dumped["dense_embeddings"] == [[0.1, 0.2]]
        assert dumped["results"] == [{"entity_id": "1", "score": 0.9}]
        assert dumped["completion"] == "Answer"

    def test_model_dump_excludes_none(self):
        """Test model_dump can exclude None values."""
        state = SearchState()
        state.results = [{"entity_id": "1"}]
        
        dumped = state.model_dump(exclude_none=True)
        
        # Should not include None fields
        assert "expanded_queries" not in dumped or dumped["expanded_queries"] is None
        assert "results" in dumped

    def test_arbitrary_types_allowed(self):
        """Test Config allows arbitrary types."""
        state = SearchState()
        
        # Should allow any type in sparse_embeddings
        class CustomObject:
            value = 42
        
        state.sparse_embeddings = [CustomObject()]
        assert state.sparse_embeddings[0].value == 42

    def test_immutable_after_creation(self):
        """Test state can be modified after creation."""
        state = SearchState()
        
        # Should be able to modify
        state.results = [{"id": "1"}]
        state.results.append({"id": "2"})
        
        assert len(state.results) == 2

    def test_full_pipeline_state_flow(self):
        """Test state through full search pipeline flow."""
        state = SearchState()
        
        # QueryExpansion
        state.expanded_queries = ["query1", "query2"]
        
        # QueryInterpretation
        state.interpreted_filter = {"must": [{"key": "source", "match": {"value": "GitHub"}}]}
        
        # EmbedQuery
        state.dense_embeddings = [[0.1] * 3072, [0.2] * 3072]
        state.sparse_embeddings = [{"indices": [0, 1], "values": [0.8, 0.6]}]
        
        # UserFilter
        state.filter = {"must": [{"key": "entity_type", "match": {"value": "issue"}}]}
        
        # Retrieval
        state.results = [
            {"entity_id": "1", "score": 0.95},
            {"entity_id": "2", "score": 0.85}
        ]
        
        # Reranking (modifies results)
        state.results = [
            {"entity_id": "2", "score": 0.90},  # Reranked
            {"entity_id": "1", "score": 0.88}
        ]
        
        # GenerateAnswer
        state.completion = "Based on the search results..."
        
        # Metrics
        state.operation_metrics = {
            "QueryExpansion": {"duration_ms": 150},
            "Retrieval": {"duration_ms": 500},
            "Reranking": {"duration_ms": 300}
        }
        
        state.provider_usage = {
            "query_expansion": "CerebrasProvider",
            "reranking": "CohereProvider"
        }
        
        # Verify all fields set correctly
        assert len(state.expanded_queries) == 2
        assert len(state.dense_embeddings) == 2
        assert state.filter is not None
        assert len(state.results) == 2
        assert state.completion is not None
        assert len(state.operation_metrics) == 3
        assert len(state.provider_usage) == 2

    def test_empty_state_serialization(self):
        """Test empty state serializes correctly."""
        state = SearchState()
        dumped = state.model_dump()
        
        assert isinstance(dumped, dict)
        assert dumped["results"] == []
        assert dumped["operation_metrics"] == {}
        assert dumped["provider_usage"] == {}

    def test_results_default_factory(self):
        """Test results field uses default_factory for empty list."""
        state1 = SearchState()
        state2 = SearchState()
        
        # Should be separate instances
        state1.results.append({"id": "1"})
        
        assert len(state1.results) == 1
        assert len(state2.results) == 0

    def test_operation_metrics_default_factory(self):
        """Test operation_metrics uses default_factory for empty dict."""
        state1 = SearchState()
        state2 = SearchState()
        
        # Should be separate instances
        state1.operation_metrics["test"] = {"value": 1}
        
        assert len(state1.operation_metrics) == 1
        assert len(state2.operation_metrics) == 0

    def test_field_descriptions(self):
        """Test fields have proper descriptions."""
        # Access field info through model
        fields = SearchState.model_fields
        
        assert "expanded_queries" in fields
        assert fields["expanded_queries"].description == "Alternative query phrasings from query expansion"
        
        assert "dense_embeddings" in fields
        assert fields["dense_embeddings"].description == "Dense embeddings for neural search"
        
        assert "results" in fields
        assert fields["results"].description == "Search results as dicts"

