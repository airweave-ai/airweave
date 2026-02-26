"""Search orchestrator.

The orchestrator is responsible for:
1. Extracting enabled operations from the search context
2. Determining execution order based on dependencies
3. Executing operations sequentially, passing state between them
4. Using the emitter from context for streaming updates
5. Automatically capturing timing metrics for each operation
"""

import time
from typing import Any, Dict, List, Set

from airweave.api.context import ApiContext
from airweave.schemas.search import SearchResponse
from airweave.search.context import SearchContext
from airweave.search.operations._base import SearchOperation
from airweave.search.state import SearchState


class SearchOrchestrator:
    """Orchestrates search operation execution.

    The orchestrator uses topological sort to determine execution order
    based on declared dependencies, then executes operations sequentially.
    """

    async def run(
        self, ctx: ApiContext, context: SearchContext
    ) -> tuple[SearchResponse, Dict[str, Any]]:
        """Execute search operations and return response with state.

        Automatically captures timing metrics for each operation and stores them
        in the state for analytics tracking.

        Returns:
            Tuple of (SearchResponse, state_dict) where state_dict contains
            operation metrics for analytics tracking.
        """
        # Get emitter from context
        emitter = context.emitter

        # Emit initial start event
        await emitter.emit(
            "start",
            {
                "request_id": context.request_id,
                "query": context.query,
                "collection_id": str(context.collection_id),
            },
        )

        # Initialize typed search state
        state = SearchState()

        # Resolve execution order
        execution_order = self._resolve_execution_order(context, ctx)

        # Execute operations in order with automatic timing
        for operation in execution_order:
            op_name = operation.__class__.__name__

            # Emit operator_start
            await emitter.emit("operator_start", {"name": op_name}, op_name=op_name)

            try:
                # Capture start time
                start_time = time.monotonic()

                # Execute operation (emitter is now in context)
                await operation.execute(context, state, ctx)

                # Capture end time and calculate duration
                duration_ms = (time.monotonic() - start_time) * 1000

                # Store timing metric automatically
                if op_name not in state.operation_metrics:
                    state.operation_metrics[op_name] = {}
                state.operation_metrics[op_name]["duration_ms"] = duration_ms

                # Emit operator_end
                await emitter.emit("operator_end", {"name": op_name}, op_name=op_name)

            except Exception as e:
                # Emit error event
                await emitter.emit(
                    "error", {"operation": op_name, "message": str(e)}, op_name=op_name
                )
                raise

        # Emit results event
        await emitter.emit("results", {"results": state.results})

        # Emit done event
        await emitter.emit("done", {"request_id": context.request_id})

        # Build response and convert state to dict for analytics
        response = SearchResponse(results=state.results, completion=state.completion)
        state_dict = state.model_dump()
        return response, state_dict

    def _resolve_execution_order(
        self, context: SearchContext, ctx: ApiContext
    ) -> List[SearchOperation]:
        """Determine execution order using topological sort."""
        # Extract enabled operations from context
        operations = self._create_list_of_enabled_operations(context)

        # Build operation name to instance mapping
        op_map = {op.__class__.__name__: op for op in operations}
        enabled_names = set(op_map.keys())

        # Build execution order using topological sort
        ordered: List[SearchOperation] = []
        visited: Set[str] = set()
        visiting: Set[str] = set()  # For cycle detection

        def visit(op_name: str) -> None:
            """Visit operation and its dependencies (DFS)."""
            if op_name in visited:
                return

            if op_name in visiting:
                raise ValueError(f"Circular dependency detected involving {op_name}")

            # Only process if operation is actually enabled
            if op_name not in enabled_names:
                return

            visiting.add(op_name)
            operation = op_map[op_name]

            # Visit all dependencies first
            for dep_name in operation.depends_on():
                visit(dep_name)

            visiting.remove(op_name)
            visited.add(op_name)
            ordered.append(operation)

        # Visit each operation
        for op_name in enabled_names:
            visit(op_name)

        # Log execution order
        op_names = [op.__class__.__name__ for op in ordered]
        ctx.logger.debug(f"[Orchestrator] Execution order: {' → '.join(op_names)}")

        return ordered

    def _create_list_of_enabled_operations(self, context: SearchContext) -> List[SearchOperation]:
        """Create a list of enabled operations from the search context."""
        operations = [
            op
            for op in [
                context.access_control_filter,
                context.query_expansion,
                context.query_interpretation,
                context.embed_query,
                context.user_filter,
                context.retrieval,
                context.federated_search,
                context.reranking,
                context.generate_answer,
            ]
            if op is not None
        ]

        return operations


orchestrator = SearchOrchestrator()
