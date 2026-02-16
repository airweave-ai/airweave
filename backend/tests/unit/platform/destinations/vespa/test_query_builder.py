"""Unit tests for Vespa QueryBuilder."""

import pytest
from uuid import UUID

from airweave.platform.destinations.vespa.query_builder import QueryBuilder
from airweave.platform.destinations.vespa.config import TARGET_HITS, HNSW_EXPLORE_ADDITIONAL


class TestQueryBuilder:
    """Test QueryBuilder constructs YQL queries and parameters."""

    # =========================================================================
    # YQL Construction - Retrieval Strategies
    # =========================================================================

    def test_build_yql_hybrid_strategy(self, query_builder, sample_collection_id):
        """Test YQL for hybrid search combines BM25 and nearestNeighbor."""
        queries = ["test query"]
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="hybrid"
        )

        # Should contain BM25 clause
        assert "userInput(@query)" in yql
        assert f"targetHits:{TARGET_HITS}" in yql

        # Should contain nearestNeighbor clause
        assert "nearestNeighbor(dense_embedding, q0)" in yql
        assert f'"hnsw.exploreAdditionalHits":{HNSW_EXPLORE_ADDITIONAL}' in yql

        # Should be combined with OR
        assert " OR " in yql

        # Should have collection filter
        assert f"airweave_system_metadata_collection_id contains '{sample_collection_id}'" in yql

    def test_build_yql_neural_strategy(self, query_builder, sample_collection_id):
        """Test YQL for neural search uses only nearestNeighbor."""
        queries = ["test query"]
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="neural"
        )

        # Should contain nearestNeighbor
        assert "nearestNeighbor(dense_embedding, q0)" in yql

        # Should NOT contain BM25
        assert "userInput" not in yql

        # Should have collection filter
        assert f"airweave_system_metadata_collection_id contains '{sample_collection_id}'" in yql

    def test_build_yql_keyword_strategy(self, query_builder, sample_collection_id):
        """Test YQL for keyword search uses only BM25."""
        queries = ["test query"]
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="keyword"
        )

        # Should contain BM25
        assert "userInput(@query)" in yql
        assert f"targetHits:{TARGET_HITS}" in yql

        # Should NOT contain nearestNeighbor
        assert "nearestNeighbor" not in yql

        # Should have collection filter
        assert f"airweave_system_metadata_collection_id contains '{sample_collection_id}'" in yql

    def test_build_yql_multiple_queries(self, query_builder, sample_collection_id):
        """Test YQL with query expansion creates multiple nearestNeighbor clauses."""
        queries = ["query 1", "query 2", "query 3"]
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="neural"
        )

        # Should have nearestNeighbor for each query
        assert "nearestNeighbor(dense_embedding, q0)" in yql
        assert "nearestNeighbor(dense_embedding, q1)" in yql
        assert "nearestNeighbor(dense_embedding, q2)" in yql

        # Should have labels
        assert 'label:"q0"' in yql
        assert 'label:"q1"' in yql
        assert 'label:"q2"' in yql

    def test_build_yql_with_filter(self, query_builder, sample_collection_id):
        """Test YQL includes filter in WHERE clause."""
        queries = ["test query"]
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"value": "GitHub"}}
            ]
        }
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=filter_dict,
            retrieval_strategy="hybrid"
        )

        # Should contain filter clause
        assert "airweave_system_metadata_source_name" in yql
        assert "GitHub" in yql

        # Should combine collection filter, retrieval clause, and user filter with AND
        assert yql.count(" AND ") >= 2

    def test_build_yql_schema_selection(self, query_builder, sample_collection_id):
        """Test YQL queries all entity schemas."""
        queries = ["test"]
        yql = query_builder.build_yql(
            queries=queries,
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="hybrid"
        )

        # Should start with select and sources
        assert yql.startswith("select * from sources")

        # Should include entity schemas
        assert "base_entity" in yql or "chunk_entity" in yql

    # =========================================================================
    # Parameter Construction
    # =========================================================================

    def test_build_params_basic(self, query_builder, sample_dense_embeddings):
        """Test basic parameter construction."""
        queries = ["test query"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        assert params["query"] == "test query"
        assert params["hits"] == 10
        assert params["offset"] == 0
        assert params["presentation.summary"] == "full"
        assert params["ranking.softtimeout.enable"] == "true"

    def test_build_params_ranking_profile_hybrid(self, query_builder, sample_dense_embeddings):
        """Test hybrid strategy selects hybrid ranking profile."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="hybrid"
        )

        assert params["ranking.profile"] == "hybrid"

    def test_build_params_ranking_profile_neural(self, query_builder, sample_dense_embeddings):
        """Test neural strategy selects semantic ranking profile."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        assert params["ranking.profile"] == "semantic"

    def test_build_params_ranking_profile_keyword(self, query_builder, sample_dense_embeddings):
        """Test keyword strategy selects keyword ranking profile."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="keyword"
        )

        assert params["ranking.profile"] == "keyword"

    def test_build_params_dense_embeddings(self, query_builder, sample_dense_embeddings):
        """Test dense embeddings added to parameters."""
        queries = ["query1", "query2"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings,
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        # Should have query(query_embedding) for ranking
        assert "ranking.features.query(query_embedding)" in params
        assert "values" in params["ranking.features.query(query_embedding)"]

        # Should have input.query(qN) for each query
        assert "input.query(q0)" in params
        assert "input.query(q1)" in params
        assert params["input.query(q0)"]["values"] == sample_dense_embeddings[0]
        assert params["input.query(q1)"]["values"] == sample_dense_embeddings[1]

    def test_build_params_sparse_embeddings(self, query_builder, sample_sparse_embedding, sample_dense_embeddings):
        """Test sparse embeddings added to parameters for hybrid/keyword."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=[sample_sparse_embedding],
            retrieval_strategy="hybrid"
        )

        # Should have sparse query tensor
        assert "input.query(q_sparse)" in params
        sparse_tensor = params["input.query(q_sparse)"]
        assert "cells" in sparse_tensor
        assert isinstance(sparse_tensor["cells"], dict)

    def test_build_params_sparse_embeddings_keyword_only(self, query_builder, sample_sparse_embedding):
        """Test sparse embeddings added for keyword strategy."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=None,
            sparse_embeddings=[sample_sparse_embedding],
            retrieval_strategy="keyword"
        )

        assert "input.query(q_sparse)" in params

    def test_build_params_sparse_embeddings_not_added_for_neural(self, query_builder, sample_sparse_embedding, sample_dense_embeddings):
        """Test sparse embeddings NOT added for neural-only strategy."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=[sample_sparse_embedding],
            retrieval_strategy="neural"
        )

        # Should NOT have sparse tensor for neural-only
        assert "input.query(q_sparse)" not in params

    def test_build_params_pagination(self, query_builder, sample_dense_embeddings):
        """Test pagination parameters."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=20,
            offset=10,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        assert params["hits"] == 20
        assert params["offset"] == 10

    def test_build_params_rerank_count(self, query_builder, sample_dense_embeddings):
        """Test rerank count covers offset + limit."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=50,
            offset=20,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="hybrid"
        )

        # Should be at least limit + offset
        rerank_count = params["ranking.globalPhase.rerankCount"]
        assert rerank_count >= 70  # 50 + 20
        # Should be at least 100 (min threshold)
        assert rerank_count >= 100

    # =========================================================================
    # Sparse Embedding Tensor Conversion
    # =========================================================================

    def test_convert_sparse_query_to_tensor_object_format(self, query_builder, sample_sparse_embedding):
        """Test sparse embedding converted to Vespa tensor object format."""
        tensor = query_builder._convert_sparse_query_to_tensor(sample_sparse_embedding)

        assert tensor is not None
        assert "cells" in tensor
        cells = tensor["cells"]

        # Should be object format (dict), not array
        assert isinstance(cells, dict)

        # Should map indices to values
        assert "0" in cells
        assert cells["0"] == 0.8
        assert "5" in cells
        assert cells["5"] == 0.6

    def test_convert_sparse_query_to_tensor_dict_input(self, query_builder):
        """Test sparse embedding conversion from dict input."""
        sparse_dict = {
            "indices": [1, 2, 3],
            "values": [0.9, 0.7, 0.5]
        }
        tensor = query_builder._convert_sparse_query_to_tensor(sparse_dict)

        assert tensor is not None
        assert "cells" in tensor
        assert tensor["cells"]["1"] == 0.9
        assert tensor["cells"]["2"] == 0.7
        assert tensor["cells"]["3"] == 0.5

    def test_convert_sparse_query_empty_indices(self, query_builder):
        """Test sparse embedding with empty indices returns None."""
        class EmptySparse:
            indices = []
            values = []

        tensor = query_builder._convert_sparse_query_to_tensor(EmptySparse())
        assert tensor is None

    def test_convert_sparse_query_invalid_input(self, query_builder):
        """Test invalid sparse embedding input returns None."""
        tensor = query_builder._convert_sparse_query_to_tensor("invalid")
        assert tensor is None

    def test_convert_sparse_query_numpy_arrays(self, query_builder):
        """Test sparse embedding with numpy arrays converted."""
        try:
            import numpy as np

            class NumpySparse:
                indices = np.array([0, 1, 2])
                values = np.array([0.8, 0.6, 0.4])

            tensor = query_builder._convert_sparse_query_to_tensor(NumpySparse())

            assert tensor is not None
            assert "cells" in tensor
            assert "0" in tensor["cells"]
        except ImportError:
            pytest.skip("NumPy not available")

    # =========================================================================
    # Query Escaping
    # =========================================================================

    def test_escape_query_basic(self, query_builder):
        """Test basic query escaping."""
        escaped = query_builder.escape_query("test query")
        assert escaped == "test query"

    def test_escape_query_with_quotes(self, query_builder):
        """Test escaping quotes in query."""
        escaped = query_builder.escape_query('query with "quotes"')
        assert r'\"' in escaped

    def test_escape_query_with_backslashes(self, query_builder):
        """Test escaping backslashes in query."""
        escaped = query_builder.escape_query(r'query\with\backslashes')
        assert r'\\' in escaped

    def test_escape_query_combined_special_chars(self, query_builder):
        """Test escaping both quotes and backslashes."""
        escaped = query_builder.escape_query(r'path\to"file"')
        assert r'\\' in escaped
        assert r'\"' in escaped

    # =========================================================================
    # Filter Translator Integration
    # =========================================================================

    def test_filter_translator_property(self, query_builder):
        """Test filter_translator property provides access to translator."""
        translator = query_builder.filter_translator
        assert translator is not None

        # Should be able to translate filters
        filter_dict = {"must": [{"key": "test", "match": {"value": "value"}}]}
        result = translator.translate(filter_dict)
        assert isinstance(result, str)

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_build_yql_empty_queries_list(self, query_builder, sample_collection_id):
        """Test YQL construction with empty queries list."""
        yql = query_builder.build_yql(
            queries=[],
            collection_id=sample_collection_id,
            filter=None,
            retrieval_strategy="hybrid"
        )

        # Should still generate valid YQL (even if empty)
        assert "select * from sources" in yql

    def test_build_params_empty_queries(self, query_builder):
        """Test params construction with empty queries list."""
        params = query_builder.build_params(
            queries=[],
            limit=10,
            offset=0,
            dense_embeddings=None,
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        # Should handle gracefully
        assert params["query"] == ""
        assert params["hits"] == 10

    def test_build_params_no_embeddings(self, query_builder):
        """Test params without embeddings (for keyword-only)."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=0,
            dense_embeddings=None,
            sparse_embeddings=None,
            retrieval_strategy="keyword"
        )

        # Should not crash, embeddings optional for keyword
        assert params["query"] == "test"
        assert "ranking.features.query(query_embedding)" not in params

    def test_build_params_large_offset(self, query_builder, sample_dense_embeddings):
        """Test params with large offset for pagination."""
        queries = ["test"]
        params = query_builder.build_params(
            queries=queries,
            limit=10,
            offset=1000,
            dense_embeddings=sample_dense_embeddings[:1],
            sparse_embeddings=None,
            retrieval_strategy="neural"
        )

        assert params["offset"] == 1000
        # Rerank count should cover offset + limit
        assert params["ranking.globalPhase.rerankCount"] >= 1010
