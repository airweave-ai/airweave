"""Unit tests for SearchOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from airweave.search.orchestrator import SearchOrchestrator
from airweave.search.state import SearchState


@pytest.fixture
def orchestrator():
    """Create SearchOrchestrator instance."""
    return SearchOrchestrator()


@pytest.fixture
def mock_context():
    """Create mock SearchContext."""
    context = MagicMock()
    context.request_id = "req-123"
    context.query = "test query"
    context.collection_id = "col-123"
    context.emitter = AsyncMock()
    
    # Mock operations
    context.access_control_filter = None
    context.query_expansion = None
    context.query_interpretation = None
    context.embed_query = None
    context.user_filter = None
    context.retrieval = None
    context.federated_search = None
    context.reranking = None
    context.generate_answer = None
    
    return context


@pytest.fixture
def mock_api_context():
    """Create mock ApiContext."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    return ctx


class TestSearchOrchestrator:
    """Test SearchOrchestrator execution and operation ordering."""

    @pytest.mark.asyncio
    async def test_run_emits_start_event(self, orchestrator, mock_context, mock_api_context):
        """Test run emits start event."""
        await orchestrator.run(mock_api_context, mock_context)
        
        # Verify start event emitted
        mock_context.emitter.emit.assert_any_call(
            "start",
            {
                "request_id": "req-123",
                "query": "test query",
                "collection_id": "col-123",
            }
        )

    @pytest.mark.asyncio
    async def test_run_emits_done_event(self, orchestrator, mock_context, mock_api_context):
        """Test run emits done event at completion."""
        await orchestrator.run(mock_api_context, mock_context)
        
        # Verify done event emitted
        mock_context.emitter.emit.assert_any_call(
            "done",
            {"request_id": "req-123"}
        )

    @pytest.mark.asyncio
    async def test_run_returns_response_and_state(self, orchestrator, mock_context, mock_api_context):
        """Test run returns SearchResponse and state dict."""
        response, state_dict = await orchestrator.run(mock_api_context, mock_context)
        
        assert response is not None
        assert isinstance(state_dict, dict)
        assert "results" in state_dict

    @pytest.mark.asyncio
    async def test_run_initializes_search_state(self, orchestrator, mock_context, mock_api_context):
        """Test run initializes SearchState."""
        response, state_dict = await orchestrator.run(mock_api_context, mock_context)
        
        # State should have default values
        assert "operation_metrics" in state_dict
        assert "provider_usage" in state_dict
        assert "results" in state_dict

    @pytest.mark.asyncio
    async def test_run_executes_operations(self, orchestrator, mock_context, mock_api_context):
        """Test run executes enabled operations."""
        # Add mock operation
        mock_op = AsyncMock()
        mock_op.execute = AsyncMock()
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "MockOperation"
        
        mock_context.retrieval = mock_op
        
        await orchestrator.run(mock_api_context, mock_context)
        
        # Verify operation executed
        mock_op.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_captures_operation_timing(self, orchestrator, mock_context, mock_api_context):
        """Test run captures timing metrics for each operation."""
        mock_op = AsyncMock()
        mock_op.execute = AsyncMock()
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "TestOp"
        
        mock_context.retrieval = mock_op
        
        response, state_dict = await orchestrator.run(mock_api_context, mock_context)
        
        # Verify timing captured
        assert "operation_metrics" in state_dict
        if "TestOp" in state_dict["operation_metrics"]:
            assert "duration_ms" in state_dict["operation_metrics"]["TestOp"]

    @pytest.mark.asyncio
    async def test_run_emits_operator_start_and_end(self, orchestrator, mock_context, mock_api_context):
        """Test run emits operator_start and operator_end events."""
        mock_op = AsyncMock()
        mock_op.execute = AsyncMock()
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "TestOp"
        
        mock_context.retrieval = mock_op
        
        await orchestrator.run(mock_api_context, mock_context)
        
        # Check for operator events
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "operator_start" in event_names
        assert "operator_end" in event_names

    @pytest.mark.asyncio
    async def test_run_emits_error_event_on_failure(self, orchestrator, mock_context, mock_api_context):
        """Test run emits error event when operation fails."""
        mock_op = AsyncMock()
        mock_op.execute = AsyncMock(side_effect=Exception("Test error"))
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "FailingOp"
        
        mock_context.retrieval = mock_op
        
        with pytest.raises(Exception):
            await orchestrator.run(mock_api_context, mock_context)
        
        # Verify error event emitted
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "error" in event_names

    def test_resolve_execution_order_single_operation(self, orchestrator, mock_context, mock_api_context):
        """Test execution order resolution with single operation."""
        mock_op = MagicMock()
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "SingleOp"
        
        mock_context.retrieval = mock_op
        
        order = orchestrator._resolve_execution_order(mock_context, mock_api_context)
        
        assert len(order) == 1
        assert order[0] == mock_op

    def test_resolve_execution_order_with_dependencies(self, orchestrator, mock_context, mock_api_context):
        """Test execution order respects dependencies."""
        op1 = MagicMock()
        op1.depends_on = MagicMock(return_value=[])
        op1.__class__.__name__ = "Op1"
        
        op2 = MagicMock()
        op2.depends_on = MagicMock(return_value=["Op1"])
        op2.__class__.__name__ = "Op2"
        
        mock_context.embed_query = op1
        mock_context.retrieval = op2
        
        order = orchestrator._resolve_execution_order(mock_context, mock_api_context)
        
        # Op1 should come before Op2
        assert len(order) == 2
        assert order[0] == op1
        assert order[1] == op2

    def test_resolve_execution_order_detects_circular_dependency(self, orchestrator, mock_context, mock_api_context):
        """Test circular dependency detection."""
        op1 = MagicMock()
        op1.depends_on = MagicMock(return_value=["Op2"])
        op1.__class__.__name__ = "Op1"
        
        op2 = MagicMock()
        op2.depends_on = MagicMock(return_value=["Op1"])
        op2.__class__.__name__ = "Op2"
        
        mock_context.embed_query = op1
        mock_context.retrieval = op2
        
        with pytest.raises(ValueError) as exc_info:
            orchestrator._resolve_execution_order(mock_context, mock_api_context)
        
        assert "Circular dependency" in str(exc_info.value)

    def test_create_list_of_enabled_operations_filters_none(self, orchestrator, mock_context):
        """Test only non-None operations are included."""
        mock_op = MagicMock()
        mock_context.retrieval = mock_op
        mock_context.reranking = None
        
        operations = orchestrator._create_list_of_enabled_operations(mock_context)
        
        assert mock_op in operations
        assert None not in operations

    def test_create_list_of_enabled_operations_includes_all_types(self, orchestrator, mock_context):
        """Test all operation types checked."""
        # Set various operations
        mock_context.query_expansion = MagicMock()
        mock_context.retrieval = MagicMock()
        mock_context.reranking = MagicMock()
        
        operations = orchestrator._create_list_of_enabled_operations(mock_context)
        
        assert len(operations) == 3

    @pytest.mark.asyncio
    async def test_run_emits_results_event(self, orchestrator, mock_context, mock_api_context):
        """Test run emits results event."""
        mock_op = AsyncMock()
        mock_op.execute = AsyncMock()
        mock_op.depends_on = MagicMock(return_value=[])
        mock_op.__class__.__name__ = "TestOp"
        
        # Mock operation that adds results
        async def add_results(context, state, ctx):
            state.results = [{"entity_id": "1", "score": 0.9}]
        
        mock_op.execute = add_results
        mock_context.retrieval = mock_op
        
        await orchestrator.run(mock_api_context, mock_context)
        
        # Verify results event emitted
        calls = [call[0] for call in mock_context.emitter.emit.call_args_list]
        event_names = [call[0] for call in calls]
        
        assert "results" in event_names

