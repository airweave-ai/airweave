"""Search factory."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings
from airweave.platform.destinations.collection_strategy import get_default_vector_size
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.token_manager import TokenManager
from airweave.schemas.search import SearchDefaults, SearchRequest
from airweave.search.context import SearchContext
from airweave.search.emitter import EventEmitter
from airweave.search.helpers import search_helpers
from airweave.search.operations import (
    EmbedQuery,
    FederatedSearch,
    GenerateAnswer,
    QueryExpansion,
    QueryInterpretation,
    Reranking,
    Retrieval,
    TemporalRelevance,
    UserFilter,
)
from airweave.search.providers._base import BaseProvider
from airweave.search.providers.cerebras import CerebrasProvider
from airweave.search.providers.cohere import CohereProvider
from airweave.search.providers.groq import GroqProvider
from airweave.search.providers.openai import OpenAIProvider
from airweave.search.providers.schemas import (
    EmbeddingModelConfig,
    LLMModelConfig,
    ProviderModelSpec,
    RerankModelConfig,
)

# Rebuild SearchContext model now that all operation classes are imported
SearchContext.model_rebuild()

defaults_data = search_helpers.load_defaults()
defaults = SearchDefaults(**defaults_data["search_defaults"])
provider_models = defaults_data.get("provider_models", {})
operation_preferences = defaults_data.get("operation_preferences", {})


class SearchFactory:
    """Create search context with provider-aware operations."""

    async def build(
        self,
        request_id: str,
        collection_id: UUID,
        readable_collection_id: str,
        search_request: SearchRequest,
        stream: bool,
        ctx: ApiContext,
        db: AsyncSession,
    ) -> SearchContext:
        """Build SearchContext from request with validated YAML defaults."""
        if not search_request.query or not search_request.query.strip():
            raise HTTPException(status_code=422, detail="Query is required")

        # Apply defaults and validate parameters
        params = self._apply_defaults_and_validate(search_request)

        # Get collection sources
        collection = await crud.collection.get(db, id=collection_id, ctx=ctx)
        federated_sources = await self.get_federated_sources(db, collection, ctx)
        has_federated_sources = bool(federated_sources)
        has_vector_sources = await self._has_vector_sources(db, collection, ctx)

        self._log_source_modes(ctx, federated_sources, has_vector_sources)

        if not has_federated_sources and not has_vector_sources:
            raise ValueError("Collection has no sources")

        # Use collection's stored vector_size for provider initialization
        vector_size = collection.vector_size

        # Fail-fast: vector_size must be set
        if vector_size is None:
            raise ValueError(f"Collection {collection.readable_id} has no vector_size set.")

        # Select providers for operations
        api_keys = self._get_available_api_keys()
        providers = self._create_provider_for_each_operation(
            api_keys, params, has_federated_sources, has_vector_sources, ctx, vector_size
        )

        # Create event emitter and emit skip notices if needed
        emitter = EventEmitter(request_id=request_id, stream=stream)
        await self._emit_skip_notices_if_needed(emitter, has_vector_sources, params, search_request)

        # Get sources that support temporal relevance (for filtering when enabled)
        temporal_supporting_sources = None
        if params["temporal_weight"] > 0 and has_vector_sources:
            try:
                temporal_supporting_sources = await self._get_temporal_supporting_sources(
                    db, collection, ctx, emitter
                )
            except Exception as e:
                # If we can't determine source support, raise the error
                raise ValueError(f"Failed to check temporal relevance support: {e}") from e

        # Build operations with vector_size
        operations = self._build_operations(
            params,
            providers,
            federated_sources,
            has_vector_sources,
            search_request,
            temporal_supporting_sources,
            vector_size,
        )

        search_context = SearchContext(
            request_id=request_id,
            collection_id=collection_id,
            readable_collection_id=readable_collection_id,
            stream=stream,
            vector_size=vector_size,
            offset=params["offset"],
            limit=params["limit"],
            emitter=emitter,
            query=search_request.query,
            **operations,
        )

        self._log_search_context(ctx, request_id, collection_id, stream, search_request, params)
        ctx.logger.info(
            f"[SearchFactory] Mode summary: has_federated={has_federated_sources}, "
            f"has_vector={has_vector_sources}"
        )

        return search_context

    def _apply_defaults_and_validate(self, search_request: SearchRequest) -> Dict[str, Any]:
        """Apply defaults to search request and validate parameters."""
        retrieval_strategy = (
            search_request.retrieval_strategy
            if search_request.retrieval_strategy is not None
            else defaults.retrieval_strategy
        )
        offset = search_request.offset if search_request.offset is not None else defaults.offset
        limit = search_request.limit if search_request.limit is not None else defaults.limit

        if offset < 0:
            raise HTTPException(status_code=422, detail="offset must be >= 0")
        if limit < 1:
            raise HTTPException(status_code=422, detail="limit must be >= 1")

        expand_query = (
            search_request.expand_query
            if search_request.expand_query is not None
            else defaults.expand_query
        )
        interpret_filters = (
            search_request.interpret_filters
            if search_request.interpret_filters is not None
            else defaults.interpret_filters
        )
        rerank = search_request.rerank if search_request.rerank is not None else defaults.rerank
        generate_answer = (
            search_request.generate_answer
            if search_request.generate_answer is not None
            else defaults.generate_answer
        )
        temporal_weight = (
            search_request.temporal_relevance
            if search_request.temporal_relevance is not None
            else defaults.temporal_relevance
        )

        if not (0 <= temporal_weight <= 1):
            raise HTTPException(
                status_code=422, detail="temporal_relevance must be between 0 and 1"
            )

        return {
            "retrieval_strategy": retrieval_strategy,
            "offset": offset,
            "limit": limit,
            "expand_query": expand_query,
            "interpret_filters": interpret_filters,
            "rerank": rerank,
            "generate_answer": generate_answer,
            "temporal_weight": temporal_weight,
        }

    def _log_source_modes(self, ctx: ApiContext, federated_sources: List, has_vector_sources: bool):
        """Log information about source modes."""
        try:
            federated_classes = [s.__class__.__name__ for s in federated_sources]
            ctx.logger.info(
                f"[SearchFactory] Federated sources (n={len(federated_classes)}): "
                f"{federated_classes}"
            )
        except Exception:
            pass
        ctx.logger.info(f"[SearchFactory] Vector-backed sources present: {has_vector_sources}")

    def _get_vector_size(self) -> int:
        """Get the default vector size for embeddings."""
        return get_default_vector_size()

    async def _emit_skip_notices_if_needed(
        self,
        emitter: EventEmitter,
        has_vector_sources: bool,
        params: Dict[str, Any],
        search_request: SearchRequest,
    ):
        """Emit skip notices for Qdrant-only features when no vector sources exist."""
        if has_vector_sources:
            return

        try:
            if params["interpret_filters"]:
                await emitter.emit(
                    "operation_skipped",
                    {
                        "operation": "QueryInterpretation",
                        "reason": "All sources in the collection use federated search",
                    },
                )
            if search_request.filter is not None:
                await emitter.emit(
                    "operation_skipped",
                    {
                        "operation": "UserFilter",
                        "reason": "All sources in the collection use federated search",
                    },
                )
            if params["temporal_weight"] > 0:
                await emitter.emit(
                    "operation_skipped",
                    {
                        "operation": "TemporalRelevance",
                        "reason": "All sources in the collection use federated search",
                    },
                )
        except Exception:
            raise ValueError("Failed to emit skip notices for Qdrant-only features")

    def _build_operations(
        self,
        params: Dict[str, Any],
        providers: Dict[str, Any],
        federated_sources: List[BaseSource],
        has_vector_sources: bool,
        search_request: SearchRequest,
        temporal_supporting_sources: Optional[List[str]] = None,
        vector_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build operation instances for the search context.

        Args:
            params: Validated search parameters from request with defaults applied
            providers: Dict with:
                - "embed": Single BaseProvider (embeddings must be consistent - no fallback)
                - Other keys: List[BaseProvider] (with fallback support)
            federated_sources: List of instantiated federated source objects
            has_vector_sources: Whether collection has any vector-backed sources
            search_request: Original search request from user
            temporal_supporting_sources: List of source short_names to filter temporal search:
                - Non-empty list: Filter to these sources (some don't support temporal)
                - Empty list: Skip operation (no sources support temporal)
                - None: No filtering needed (temporal disabled or not checked)
            vector_size: Vector dimensions for this collection (used by EmbedQuery)
        """
        return {
            "query_expansion": (
                QueryExpansion(providers=providers["expansion"]) if params["expand_query"] else None
            ),
            "query_interpretation": (
                QueryInterpretation(providers=providers["interpretation"])
                if (params["interpret_filters"] and has_vector_sources)
                else None
            ),
            "embed_query": (
                EmbedQuery(
                    strategy=params["retrieval_strategy"],
                    provider=providers["embed"],  # Single provider - embeddings must be consistent
                    vector_size=vector_size,
                )
                if has_vector_sources
                else None
            ),
            "temporal_relevance": (
                TemporalRelevance(
                    weight=params["temporal_weight"], supporting_sources=temporal_supporting_sources
                )
                if (
                    params["temporal_weight"] > 0
                    and has_vector_sources
                    # Skip only if explicitly empty list (no sources support it)
                    and temporal_supporting_sources != []
                )
                else None
            ),
            "user_filter": (
                UserFilter(filter=search_request.filter)
                if (search_request.filter and has_vector_sources)
                else None
            ),
            "retrieval": (
                Retrieval(
                    strategy=params["retrieval_strategy"],
                    offset=params["offset"],
                    limit=params["limit"],
                )
                if has_vector_sources
                else None
            ),
            "federated_search": (
                FederatedSearch(
                    sources=federated_sources,
                    limit=params["limit"],
                    providers=providers["federated"],  # List of providers with fallback
                )
                if federated_sources
                else None
            ),
            "reranking": (Reranking(providers=providers["rerank"]) if params["rerank"] else None),
            "generate_answer": (
                GenerateAnswer(providers=providers["answer"]) if params["generate_answer"] else None
            ),
        }

    def _log_search_context(
        self,
        ctx: ApiContext,
        request_id: str,
        collection_id: UUID,
        stream: bool,
        search_request: SearchRequest,
        params: Dict[str, Any],
    ):
        """Log search context configuration."""
        ctx.logger.debug(
            f"[SearchFactory] Built search context: \n"
            f"request_id={request_id}, \n"
            f"collection_id={collection_id}, \n"
            f"stream={stream}, \n"
            f"query='{search_request.query[:50]}...', \n"
            f"retrieval_strategy={params['retrieval_strategy']}, \n"
            f"offset={params['offset']}, \n"
            f"limit={params['limit']}, "
            f"temporal_weight={params['temporal_weight']}, \n"
            f"expand_query={params['expand_query']}, \n"
            f"interpret_filters={params['interpret_filters']}, \n"
            f"rerank={params['rerank']}, \n"
            f"generate_answer={params['generate_answer']}, \n"
        )

    def _get_available_api_keys(self) -> Dict[str, Optional[str]]:
        """Get available API keys from settings."""
        return {
            "cerebras": getattr(settings, "CEREBRAS_API_KEY", None),
            "groq": getattr(settings, "GROQ_API_KEY", None),
            "openai": getattr(settings, "OPENAI_API_KEY", None),
            "cohere": getattr(settings, "COHERE_API_KEY", None),
        }

    def _create_provider_for_each_operation(
        self,
        api_keys: Dict[str, Optional[str]],
        params: Dict[str, Any],
        has_federated_sources: bool,
        has_vector_sources: bool,
        ctx: ApiContext,
        vector_size: int,
    ) -> Dict[str, BaseProvider]:
        """Select and validate all required providers."""
        providers = {}

        # Create embedding provider if needed
        if has_vector_sources:
            providers["embed"] = self._create_embedding_provider(api_keys, ctx, vector_size)

        # Create LLM providers for enabled operations
        providers.update(
            self._create_llm_providers(
                api_keys, params, has_federated_sources, has_vector_sources, ctx
            )
        )

        ctx.logger.debug(f"[SearchFactory] Providers: {providers}")
        return providers

    def _create_embedding_provider(
        self, api_keys: Dict[str, Optional[str]], ctx: ApiContext, vector_size: int
    ) -> BaseProvider:
        """Create embedding provider for vector-backed search.

        Note: Returns single provider, not a list. Embeddings must use consistent
        models within a collection and cannot fallback to different providers.
        """
        providers = self._init_all_providers_for_operation(
            "embed_query", api_keys, ctx, vector_size
        )
        if not providers:
            raise ValueError(
                "Embedding provider required for vector-backed search. Configure OPENAI_API_KEY"
            )
        # Return first (and only) available embedding provider
        return providers[0]

    def _create_llm_providers(
        self,
        api_keys: Dict[str, Optional[str]],
        params: Dict[str, Any],
        has_federated_sources: bool,
        has_vector_sources: bool,
        ctx: ApiContext,
    ) -> Dict[str, List[BaseProvider]]:
        """Create LLM provider lists for enabled operations.

        Returns dict mapping operation keys to lists of providers in preference order.
        """
        providers = {}

        # Query expansion
        if params["expand_query"]:
            self._add_provider_list_or_error(
                providers,
                "expansion",
                "query_expansion",
                api_keys,
                ctx,
                "Query expansion enabled but no provider available. "
                "Configure CEREBRAS_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY",
            )

        # Federated search
        if has_federated_sources:
            self._add_provider_list_or_error(
                providers,
                "federated",
                "federated_search",
                api_keys,
                ctx,
                "Federated sources exist but no provider available for keyword extraction. "
                "Configure CEREBRAS_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY",
            )

        # Query interpretation
        if params["interpret_filters"] and has_vector_sources:
            self._add_provider_list_or_error(
                providers,
                "interpretation",
                "query_interpretation",
                api_keys,
                ctx,
                "Query interpretation enabled but no provider available. "
                "Configure CEREBRAS_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY",
            )

        # Reranking
        if params["rerank"]:
            self._add_provider_list_or_error(
                providers,
                "rerank",
                "reranking",
                api_keys,
                ctx,
                "Reranking enabled but no provider available. "
                "Configure COHERE_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY",
            )

        # Answer generation
        if params["generate_answer"]:
            self._add_provider_list_or_error(
                providers,
                "answer",
                "generate_answer",
                api_keys,
                ctx,
                "Answer generation enabled but no provider available. "
                "Configure CEREBRAS_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY",
            )

        return providers

    def _add_provider_list_or_error(
        self,
        providers: Dict[str, List[BaseProvider]],
        key: str,
        operation_name: str,
        api_keys: Dict[str, Optional[str]],
        ctx: ApiContext,
        error_message: str,
    ):
        """Add a provider list to the dict or raise an error if none available."""
        provider_list = self._init_all_providers_for_operation(operation_name, api_keys, ctx)
        if not provider_list:
            raise ValueError(error_message)
        providers[key] = provider_list
        ctx.logger.debug(
            f"[SearchFactory] Initialized {len(provider_list)} provider(s) for {operation_name}"
        )

    async def _has_vector_sources(self, db: AsyncSession, collection, ctx: ApiContext) -> bool:
        """Return True if collection has any non-federated (vector-backed) sources."""
        try:
            source_connections = await crud.source_connection.get_for_collection(
                db, readable_collection_id=collection.readable_id, ctx=ctx
            )
            if not source_connections:
                return False

            for source_connection in source_connections:
                source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
                if not source_model:
                    raise ValueError(f"Source model not found for {source_connection.short_name}")
                source_class = resource_locator.get_source(source_model)
                if not getattr(source_class, "_federated_search", False):
                    return True
            return False
        except Exception:
            raise ValueError(
                f"Error getting vector sources for collection {collection.readable_id}"
            )

    async def _get_temporal_supporting_sources(
        self, db: AsyncSession, collection, ctx: ApiContext, emitter: EventEmitter
    ) -> List[str]:
        """Get list of source short_names that support temporal relevance.

        Args:
            db: Database session
            collection: Collection object
            ctx: API context
            emitter: Event emitter for skip notices

        Returns:
            - Non-empty list: Some/all sources support temporal relevance (apply filtering)
            - Empty list []: No sources support it (caller should skip operation)

        Raises:
            ValueError: If source connections or models cannot be retrieved
        """
        source_connections = await crud.source_connection.get_for_collection(
            db, readable_collection_id=collection.readable_id, ctx=ctx
        )
        if not source_connections:
            raise ValueError(f"No source connections found for collection {collection.readable_id}")

        supporting_sources = []
        non_supporting_sources = []

        for source_connection in source_connections:
            source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
            if not source_model:
                raise ValueError(
                    f"Source model not found for short_name={source_connection.short_name}"
                )

            # Check if source supports temporal relevance
            supports_temporal = getattr(source_model, "supports_temporal_relevance", True)

            if supports_temporal:
                supporting_sources.append(source_connection.short_name)
            else:
                non_supporting_sources.append(source_connection.short_name)

        # Log the results
        if supporting_sources:
            ctx.logger.info(
                f"[SearchFactory] Temporal relevance: {len(supporting_sources)} "
                f"supporting source(s): {supporting_sources}"
            )
        if non_supporting_sources:
            ctx.logger.info(
                f"[SearchFactory] Temporal relevance: {len(non_supporting_sources)} "
                f"non-supporting source(s) will be filtered out: {non_supporting_sources}"
            )

        # If no sources support temporal relevance, emit skip event and return empty list
        if not supporting_sources:
            await emitter.emit(
                "operation_skipped",
                {
                    "operation": "TemporalRelevance",
                    "reason": "no_sources_support_temporal_relevance",
                    "non_supporting_sources": non_supporting_sources,
                },
            )
            ctx.logger.warning(
                f"[SearchFactory] No sources in collection support temporal relevance. "
                f"Skipping temporal decay. Non-supporting sources: {non_supporting_sources}"
            )
            return []  # Empty list signals "skip operation"

        return supporting_sources

    def _init_all_providers_for_operation(
        self,
        operation_name: str,
        api_keys: Dict[str, Optional[str]],
        ctx: ApiContext,
        vector_size: Optional[int] = None,
    ) -> List[BaseProvider]:
        """Initialize ALL available providers for an operation in preference order.

        Returns list of working providers that can be used for fallback.
        Operations will try providers in order until one succeeds.

        Args:
            operation_name: Name of the operation (e.g., "embed_query")
            api_keys: Dict of provider API keys
            ctx: API context
            vector_size: Optional vector dimensions for embedding model selection
        """
        preferences = operation_preferences.get(operation_name, {})
        order = preferences.get("order", [])

        initialized_providers: List[BaseProvider] = []

        # Try each provider in preference order
        for entry in order:
            provider_name = entry.get("provider")
            if not provider_name:
                # Skip malformed entries
                continue

            api_key = api_keys.get(provider_name)
            if not api_key:
                # API key not available for this provider, try next
                continue

            # Get provider's model specifications
            provider_spec = provider_models.get(provider_name, {})

            # Build model configs for each type
            llm_config = self._build_llm_config(provider_spec, entry.get("llm"))
            embedding_config = self._build_embedding_config_for_vector_size(
                provider_spec, entry.get("embedding"), vector_size
            )
            rerank_config = self._build_rerank_config(provider_spec, entry.get("rerank"))

            model_spec = ProviderModelSpec(
                llm_model=llm_config,
                embedding_model=embedding_config,
                rerank_model=rerank_config,
            )

            # Initialize provider with complete model spec
            try:
                provider = None
                if provider_name == "cerebras":
                    ctx.logger.debug(
                        f"[Factory] Attempting to initialize CerebrasProvider for {operation_name}"
                    )
                    provider = CerebrasProvider(api_key=api_key, model_spec=model_spec, ctx=ctx)
                elif provider_name == "groq":
                    ctx.logger.debug(
                        f"[Factory] Attempting to initialize GroqProvider for {operation_name}"
                    )
                    provider = GroqProvider(api_key=api_key, model_spec=model_spec, ctx=ctx)
                elif provider_name == "openai":
                    ctx.logger.debug(
                        f"[Factory] Attempting to initialize OpenAIProvider for {operation_name}"
                    )
                    provider = OpenAIProvider(api_key=api_key, model_spec=model_spec, ctx=ctx)
                elif provider_name == "cohere":
                    ctx.logger.debug(
                        f"[Factory] Attempting to initialize CohereProvider for {operation_name}"
                    )
                    provider = CohereProvider(api_key=api_key, model_spec=model_spec, ctx=ctx)

                if provider:
                    initialized_providers.append(provider)
                    ctx.logger.debug(
                        f"[Factory] Successfully initialized {provider_name} for {operation_name}"
                    )
            except Exception as e:
                # Provider initialization failed (bad API key, missing tokenizer, etc.)
                # Continue with next provider - don't add to list
                ctx.logger.warning(
                    f"[Factory] Failed to initialize {provider_name} for {operation_name}: {e}"
                )
                continue

        return initialized_providers

    def _build_llm_config(
        self, provider_spec: dict, model_key: Optional[str]
    ) -> Optional[LLMModelConfig]:
        """Build LLMModelConfig from provider spec."""
        if not model_key:
            return None

        model_dict = provider_spec.get(model_key)
        if not model_dict:
            return None

        return LLMModelConfig(**model_dict)

    def _build_embedding_config(
        self, provider_spec: dict, model_key: Optional[str]
    ) -> Optional[EmbeddingModelConfig]:
        """Build EmbeddingModelConfig from provider spec."""
        if not model_key:
            return None

        model_dict = provider_spec.get(model_key)
        if not model_dict:
            return None

        return EmbeddingModelConfig(**model_dict)

    def _build_embedding_config_for_vector_size(
        self, provider_spec: dict, model_key: Optional[str], vector_size: Optional[int]
    ) -> Optional[EmbeddingModelConfig]:
        """Build EmbeddingModelConfig by selecting the right model key from defaults.yml.

        For OpenAI embeddings, selects between embedding_small and embedding_large:
        - 3072: uses embedding_large (text-embedding-3-large)
        - 1536: uses embedding_small (text-embedding-3-small)
        - Other: uses the provided model_key (e.g., "embedding" as fallback)

        Args:
            provider_spec: Provider specification from defaults.yml
            model_key: Key to look up model config (e.g., "embedding")
            vector_size: Vector dimensions for this collection

        Returns:
            EmbeddingModelConfig from the appropriate model key, or None if not applicable
        """
        if not model_key:
            return None

        # For OpenAI provider, select the right model key based on vector_size
        actual_model_key = model_key
        if vector_size == 3072:
            actual_model_key = "embedding_large"
        elif vector_size == 1536:
            actual_model_key = "embedding_small"
        # else: use provided model_key (fallback to "embedding" for other sizes)

        model_dict = provider_spec.get(actual_model_key)
        if not model_dict:
            # Fallback to original model_key if specific one not found
            model_dict = provider_spec.get(model_key)
            if not model_dict:
                return None

        return EmbeddingModelConfig(**model_dict)

    def _build_rerank_config(
        self, provider_spec: dict, model_key: Optional[str]
    ) -> Optional[RerankModelConfig]:
        """Build RerankModelConfig from provider spec."""
        if not model_key:
            return None

        model_dict = provider_spec.get(model_key)
        if not model_dict:
            return None

        return RerankModelConfig(**model_dict)

    async def get_federated_sources(
        self, db: AsyncSession, collection, ctx: ApiContext
    ) -> List[BaseSource]:
        """Get instantiated federated sources for a collection.

        Args:
            db: Database session
            collection: Collection object
            ctx: API context

        Returns:
            List of instantiated source objects that support federated search
        """
        try:
            source_connections = await crud.source_connection.get_for_collection(
                db, readable_collection_id=collection.readable_id, ctx=ctx
            )

            if not source_connections:
                return []

            federated_sources = []
            for source_connection in source_connections:
                source_instance = await self._try_instantiate_federated_source(
                    db, source_connection, ctx
                )
                if source_instance:
                    federated_sources.append(source_instance)

            return federated_sources

        except Exception as e:
            raise ValueError(f"Error getting federated sources: {e}")

    async def _try_instantiate_federated_source(
        self, db: AsyncSession, source_connection, ctx: ApiContext
    ) -> Optional[BaseSource]:
        """Try to instantiate a federated source from a source connection."""
        try:
            # Check if source supports federated search
            source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
            if not source_model:
                ctx.logger.warning(f"Source model not found for {source_connection.short_name}")
                return None

            source_class = resource_locator.get_source(source_model)
            if not getattr(source_class, "_federated_search", False):
                return None

            ctx.logger.info(
                f"Found federated source: {source_connection.short_name} "
                f"(id: {source_connection.id})"
            )

            # Get credentials and create source instance
            credentials_data = await self._get_source_credentials(db, source_connection, ctx)
            source_instance = await source_class.create(
                credentials_data["access_token"], config=source_connection.config_fields
            )

            # Configure source instance
            if hasattr(source_instance, "set_logger"):
                source_instance.set_logger(ctx.logger)

            # Setup token manager if needed
            if source_model.oauth_type and isinstance(credentials_data["decrypted"], dict):
                self._setup_token_manager(
                    source_instance,
                    db,
                    source_connection,
                    credentials_data["connection"],
                    credentials_data["decrypted"],
                    ctx,
                )

            ctx.logger.info(
                f"Successfully instantiated federated source: {source_connection.short_name}"
            )
            return source_instance

        except Exception as e:
            raise ValueError(
                f"Error instantiating federated source {source_connection.short_name}: {e}"
            )

    async def _get_source_credentials(
        self, db: AsyncSession, source_connection, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Get and decrypt credentials for a source connection."""
        connection = await crud.connection.get(db, source_connection.connection_id, ctx)
        if not connection or not connection.integration_credential_id:
            raise ValueError(f"No credentials found for source connection {source_connection.id}")

        credential = await crud.integration_credential.get(
            db, connection.integration_credential_id, ctx
        )
        if not credential:
            raise ValueError(f"No credentials found for source connection {source_connection.id}")

        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        # Extract access token
        access_token = None
        if isinstance(decrypted_credential, dict):
            access_token = decrypted_credential.get("access_token")
        elif isinstance(decrypted_credential, str):
            access_token = decrypted_credential

        if not access_token:
            raise ValueError(f"No access token found for source {source_connection.short_name}")

        return {
            "access_token": access_token,
            "decrypted": decrypted_credential,
            "connection": connection,
        }

    def _setup_token_manager(
        self,
        source_instance: BaseSource,
        db: AsyncSession,
        source_connection,
        connection,
        decrypted_credential: dict,
        ctx: ApiContext,
    ):
        """Setup token manager for OAuth sources."""
        minimal_connection = type(
            "MinimalConnection",
            (),
            {
                "id": connection.id,
                "integration_credential_id": connection.integration_credential_id,
                "config_fields": source_connection.config_fields,
            },
        )()

        token_manager = TokenManager(
            db=db,
            source_short_name=source_connection.short_name,
            source_connection=minimal_connection,
            ctx=ctx,
            initial_credentials=decrypted_credential,
            is_direct_injection=False,
            logger_instance=ctx.logger,
        )
        source_instance.set_token_manager(token_manager)


factory = SearchFactory()
