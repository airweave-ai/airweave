"""Search executor module.

The executor is responsible for running the operations in the correct
order based on their dependencies, handling errors, and managing timeouts.
"""

# import asyncio  # Will be used for parallel execution
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.analytics.service import analytics
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.pubsub import core_pubsub
from airweave.schemas.search import SearchConfig
from airweave.search.operations.base import SearchOperation


class SearchExecutor:
    """Executes search operations in dependency order.

    The executor takes a list of operations and executes them in the
    correct order based on their dependencies. It handles:
    - Dependency resolution and execution ordering
    - Parallel execution where possible
    - Error handling for optional operations
    - Timeout management
    - Context passing between operations

    The executor is stateless and can be reused across requests.
    """

    async def execute(  # noqa: C901 - orchestrates full pipeline, acceptable complexity
        self,
        config: SearchConfig,
        db: AsyncSession,
        ctx: ApiContext,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute operations and return the final context.

        This method runs all operations in dependency order, passing
        a shared context dictionary between them. The context accumulates
        data as operations execute.

        Args:
            config: Search configuration with operations
            db: Database session
            ctx: API context with logger
            request_id: Optional streaming request identifier. When provided, lifecycle
                and data events are published to ``search:<request_id>`` via Redis.

        Returns:
            Final context dictionary with all operation results

        Raises:
            Exception: If a non-optional operation fails

        Notes:
            If ``request_id`` is provided, lifecycle and data events are published to
            the ``search:<request_id>`` Redis channel via the unified pubsub helper.
        """
        # Extract operations from config fields
        operations = self._extract_operations_from_config(config)

        # Initialize context with common data
        context = self._initialize_context(config, db, ctx)
        # Attach request id for streaming (if present)
        if request_id:
            context["request_id"] = request_id
            # In streaming mode, any operator failure should fail the entire search
            context["streaming_required"] = True

        # Log configuration summary
        try:
            ctx.logger.debug(
                "[SearchExecutor] Config summary: "
                f"limit={config.limit}, offset={config.offset}, "
                f"score_threshold={config.score_threshold}, "
                f"ops={{"
                f"query_interpretation={'on' if config.query_interpretation else 'off'}, "
                f"query_expansion={'on' if config.query_expansion else 'off'}, "
                f"qdrant_filter={'on' if config.qdrant_filter else 'off'}, "
                f"embedding=on, vector_search=on, "
                f"recency={'on' if getattr(config, 'recency', None) else 'off'}, "
                f"reranking={'on' if config.reranking else 'off'}, "
                f"completion={'on' if config.completion else 'off'}"
                f"}}"
            )
        except Exception:
            pass

        # Centralized emitter: installs an async emit() on context used by all operators
        op_sequences: Dict[str, int] = {}
        global_sequence: int = 0
        emit_lock = asyncio.Lock()

        async def emit(
            event_type: str, data: Dict[str, Any], op_name: Optional[str] = None
        ) -> None:
            nonlocal global_sequence
            if not request_id:
                return
            try:
                async with emit_lock:
                    global_sequence += 1
                    seq = global_sequence
                    op_seq_val = None
                    if op_name:
                        op_sequences[op_name] = op_sequences.get(op_name, 0) + 1
                        op_seq_val = op_sequences[op_name]

                payload: Dict[str, Any] = {
                    "type": event_type,
                    "seq": seq,
                    "op": op_name,
                    "op_seq": op_seq_val,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    **data,
                }
                await core_pubsub.publish("search", request_id, payload)
            except Exception:
                # Never fail pipeline due to streaming issues
                pass

        context["emit"] = emit

        # Emit start lifecycle event
        await emit(
            "start",
            {
                "request_id": request_id,
                "query": config.query,
                "limit": config.limit,
                "offset": config.offset,
            },
        )

        # Track execution state
        executed = set()
        start_time = time.time()

        try:
            # Execute operations in dependency order
            while len(executed) < len(operations):
                # Find operations ready to execute
                ready = self._find_ready_operations(operations, executed)

                if not ready:
                    # No more operations can execute
                    if len(executed) < len(operations):
                        remaining = [op.name for op in operations if op.name not in executed]
                        ctx.logger.warning(
                            "[SearchExecutor] Cannot execute remaining operations: %s",
                            remaining,
                        )
                    break

                # Execute ready operations (could be parallelized in future)
                for op in ready:
                    try:
                        # Emit operator_start
                        await emit("operator_start", {"name": op.name}, op_name=op.name)
                        # Execute with timing
                        op_start = time.time()
                        await op.execute(context)
                        op_time = (time.time() - op_start) * 1000

                        context["timings"][op.name] = op_time
                        executed.add(op.name)

                        ctx.logger.debug(
                            f"[SearchExecutor] Operation {op.name} completed in {op_time:.2f}ms"
                        )

                        # Emit operator_end
                        await emit(
                            "operator_end", {"name": op.name, "ms": op_time}, op_name=op.name
                        )

                        # Log intermediate state snapshot for key artifacts
                        try:
                            snapshot = {
                                "expanded_queries": len(context.get("expanded_queries", []))
                                if isinstance(context.get("expanded_queries"), list)
                                else (1 if context.get("expanded_queries") else 0),
                                "embeddings": len(context.get("embeddings", []))
                                if isinstance(context.get("embeddings"), list)
                                else 0,
                                "has_filter": bool(context.get("filter")),
                                "raw_results": len(context.get("raw_results", []))
                                if isinstance(context.get("raw_results"), list)
                                else 0,
                                "final_results": len(context.get("final_results", []))
                                if isinstance(context.get("final_results"), list)
                                else 0,
                                "has_completion": bool(context.get("completion")),
                            }
                            ctx.logger.debug(f"[SearchExecutor] State after {op.name}: {snapshot}")
                        except Exception:
                            pass

                    except Exception as e:
                        # Log the error and always fail the search
                        ctx.logger.error(
                            f"[SearchExecutor] Operation {op.name} failed: {e}", exc_info=True
                        )
                        context["errors"].append({"operation": op.name, "error": str(e)})

                        # Emit error event if streaming emitter is present
                        await emit(
                            "error", {"operation": op.name, "message": str(e)}, op_name=op.name
                        )
                        # Propagate failure (both streaming and non-streaming)
                        raise

            # Ensure we have final results
            self._finalize_context(context)

            # Emit results (raw as produced by pipeline)
            await emit("results", {"results": context.get("final_results", [])})

            # Log execution summary
            total_time = (time.time() - start_time) * 1000
            ctx.logger.debug(
                f"[SearchExecutor] Search completed in {total_time:.2f}ms, "
                f"executed {len(executed)}/{len(operations)} operations"
            )

            # Emit summary
            await emit(
                "summary",
                {
                    "timings": context.get("timings", {}),
                    "errors": context.get("errors", []),
                    "total_time_ms": total_time,
                },
            )
        finally:
            # Track search completion analytics
            if ctx:
                # Extract search context from the execution context
                query = context.get("query", "")
                collection_slug = context.get("collection_slug", "")
                search_duration_ms = (time.time() - start_time) * 1000

                # Determine search type
                search_type = "streaming" if request_id else "regular"

                # Track search completion directly with global analytics service
                properties = {
                    "query_length": len(query),
                    "collection_slug": collection_slug,
                    "duration_ms": search_duration_ms,
                    "search_type": search_type,
                    "organization_name": getattr(ctx.organization, "name", "unknown"),
                    "status": "success",
                }

                # Add results count if available
                final_results = context.get("final_results")
                if final_results:
                    properties["results_count"] = len(final_results)

                # Track the event using global analytics service
                analytics.track_event(
                    event_name="search_query",
                    distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
                    properties=properties,
                    groups={"organization": str(ctx.organization.id)},
                )

            # Always emit done so clients can close streams reliably
            await emit("done", {"request_id": request_id})

        return context

    def _initialize_context(
        self, config: SearchConfig, db: AsyncSession, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Initialize the context dictionary.

        Creates the initial context with all common data that operations
        might need. Operations will add their results to this context.

        Args:
            config: Search configuration
            db: Database session
            ctx: API context

        Returns:
            Initialized context dictionary
        """
        return {
            # Core data
            "query": config.query,
            "config": config,
            "db": db,
            "ctx": ctx,
            "logger": ctx.logger,
            # API keys and settings
            "openai_api_key": settings.OPENAI_API_KEY
            if hasattr(settings, "OPENAI_API_KEY")
            else None,
            # Tracking
            "timings": {},
            "errors": [],
            # Results (will be populated by operations)
            # expanded_queries: List[str]
            # embeddings: List[List[float]]
            # filter: Dict
            # raw_results: List[Dict]
            # final_results: List[Dict]
            # completion: str
        }

    def _find_ready_operations(
        self, operations: List[SearchOperation], executed: Set[str]
    ) -> List[SearchOperation]:
        """Find operations that are ready to execute.

        An operation is ready if:
        - It hasn't been executed yet
        - All its dependencies have been executed

        Args:
            operations: All operations
            executed: Set of already executed operation names

        Returns:
            List of operations ready to execute
        """
        ready = []

        for op in operations:
            if op.name in executed:
                continue

            # Check if all dependencies are satisfied
            # Note: We're lenient here - if a dependency doesn't exist
            # in the plan, we assume it's optional and continue
            deps_satisfied = all(
                dep in executed or not self._operation_exists(operations, dep)
                for dep in op.depends_on
            )

            if deps_satisfied:
                ready.append(op)

        return ready

    def _operation_exists(self, operations: List[SearchOperation], name: str) -> bool:
        """Check if an operation exists in the plan.

        Args:
            operations: List of operations
            name: Operation name to check

        Returns:
            True if operation exists
        """
        return any(op.name == name for op in operations)

    def _extract_operations_from_config(self, config: SearchConfig) -> List[SearchOperation]:
        """Extract enabled operations from config fields.

        The executor is responsible for determining which operations
        are enabled and what order to execute them in, not the config.

        Args:
            config: SearchConfig with operation fields

        Returns:
            List of enabled operations
        """
        operations = []

        # Extract operations from config fields in logical order
        # The order here represents the typical execution flow

        # 1. Query expansion (optional) — run BEFORE interpretation so interpretation
        #    can leverage all phrasings to derive higher-quality filters
        if config.query_expansion:
            operations.append(config.query_expansion)

        # 2. Query interpretation (optional)
        if config.query_interpretation:
            operations.append(config.query_interpretation)

        # 3. Qdrant filter (optional)
        if config.qdrant_filter:
            operations.append(config.qdrant_filter)

        # 4. Embedding (required)
        operations.append(config.embedding)

        # 5. Vector search (required)
        operations.append(config.vector_search)

        # 6. Dynamic recency (optional)
        if getattr(config, "recency", None):
            operations.append(config.recency)

        # 7. Reranking (optional)
        if config.reranking:
            operations.append(config.reranking)

        # 8. Completion (optional)
        if config.completion:
            operations.append(config.completion)

        return operations

    def _finalize_context(self, context: Dict[str, Any]) -> None:
        """Ensure context has required final fields.

        Makes sure the context has final_results even if reranking
        didn't run, and handles other finalization tasks.

        Args:
            context: Context to finalize
        """
        # Ensure we have final_results
        if "final_results" not in context:
            # Use raw_results as final if no reranking
            context["final_results"] = context.get("raw_results", [])

        # Add execution summary
        context["execution_summary"] = {
            "operations_executed": len(context["timings"]),
            "total_time_ms": sum(context["timings"].values()),
            "errors_count": len(context["errors"]),
        }

    async def _emit(self, context: Dict[str, Any], event_type: str, data: Dict[str, Any]) -> None:
        """Compatibility shim: use centralized emitter if available."""
        emitter = context.get("emit")
        if callable(emitter):
            await emitter(event_type, data)

    # Note: cleaning of results is handled at response-building level, not during streaming
