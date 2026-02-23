"""Search factory."""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.domains.embedders.protocols import EmbedderServiceProtocol
from airweave.domains.embedders.service import EmbedderService
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.utils.source_factory_utils import (
    get_auth_configuration,
    process_credentials_for_source,
)
from airweave.schemas.search import RetrievalStrategy, SearchDefaults, SearchRequest
from airweave.search.context import SearchContext
from airweave.search.emitter import EventEmitter
from airweave.search.helpers import search_helpers
from airweave.search.operations import (
    AccessControlFilter,
    EmbedQuery,
    FederatedSearch,
    GenerateAnswer,
    QueryExpansion,
    QueryInterpretation,
    Reranking,
    Retrieval,
    UserFilter,
)
from airweave.search.providers._base import BaseProvider
from airweave.search.providers.cerebras import CerebrasProvider
from airweave.search.providers.cohere import CohereProvider
from airweave.search.providers.groq import GroqProvider
from airweave.search.providers.mistral import MistralProvider
from airweave.search.providers.openai import OpenAIProvider
from airweave.search.providers.schemas import (
    EmbeddingModelConfig,
    LLMModelConfig,
    ProviderModelSpec,
    RerankModelConfig,
)

# Type alias for destination override
DestinationOverride = Literal["vespa"]

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
        embedder_service: EmbedderServiceProtocol,
        # --- Optional parameters for admin/ACL search ---
        destination_override: Optional[DestinationOverride] = None,
        user_principal_override: Optional[str] = None,
        skip_organization_check: bool = False,
    ) -> SearchContext:
        """Build SearchContext from request with validated YAML defaults.

        Args:
            request_id: Unique request identifier
            collection_id: Collection UUID
            readable_collection_id: Human-readable collection ID
            search_request: Search parameters
            stream: Whether to enable SSE streaming
            ctx: API context with auth info
            db: Database session
            embedder_service: Embedder service for generating query embeddings
            destination_override: Override destination ("vespa").
                If None, uses Vespa (default).
            user_principal_override: Username to use for ACL filtering.
                If None, uses ctx.user for ACL (normal behavior).
            skip_organization_check: If True, skip organization filtering when
                fetching collection (for admin cross-org access).

        Returns:
            Configured SearchContext ready for orchestration
        """
        # Enrich logger with collection context for all downstream logs
        ctx.logger = ctx.logger.with_context(collection=readable_collection_id)

        if not search_request.query or not search_request.query.strip():
            raise HTTPException(status_code=422, detail="Query is required")

        # Apply defaults and validate parameters
        params = self._apply_defaults_and_validate(search_request, ctx)

        # Get collection - with or without organization filtering
        if skip_organization_check:
            from airweave.models.collection import Collection

            result = await db.execute(sa_select(Collection).where(Collection.id == collection_id))
            collection = result.scalar_one_or_none()
        else:
            collection = await crud.collection.get(db, id=collection_id, ctx=ctx)

        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        # Resolve query-time embedder: use collection's stored model if available
        query_embedder = self._resolve_query_embedder(collection, embedder_service, ctx)

        federated_sources = await self.get_federated_sources(db, collection, ctx)
        has_federated_sources = bool(federated_sources)
        has_vector_sources = await self._has_vector_sources(db, collection, ctx)

        # Resolve destination (may be overridden for admin search)
        destination = await self._resolve_destination(db, collection, ctx, destination_override)
        requires_embedding = getattr(destination, "requires_client_embedding", True)

        self._log_source_modes(ctx, federated_sources, has_vector_sources)
        ctx.logger.info(
            f"[SearchFactory] Destination: {destination.__class__.__name__}, "
            f"requires_client_embedding: {requires_embedding}"
        )

        if not has_federated_sources and not has_vector_sources:
            raise ValueError("Collection has no sources")

        # Use query embedder's vector size (from collection's model or global config)
        vector_size = query_embedder.vector_size

        # Select providers for operations (LLM, rerank — NOT embedding)
        api_keys = self._get_available_api_keys()
        providers = self._create_provider_for_each_operation(
            api_keys,
            params,
            has_federated_sources,
            has_vector_sources,
            ctx,
            requires_client_embedding=requires_embedding,
        )

        # Create event emitter and emit skip notices if needed
        emitter = EventEmitter(request_id=request_id, stream=stream)
        await self._emit_skip_notices_if_needed(emitter, has_vector_sources, params, search_request)

        # Build operations with destination (destination-agnostic)
        operations = self._build_operations(
            params,
            providers,
            federated_sources,
            has_vector_sources,
            search_request,
            vector_size,
            destination=destination,
            requires_client_embedding=requires_embedding,
            db=db,
            ctx=ctx,
            user_principal_override=user_principal_override,
            organization_id=collection.organization_id,
            embedder_service=query_embedder,
        )

        search_context = SearchContext(
            request_id=request_id,
            collection_id=collection_id,
            readable_collection_id=readable_collection_id,
            stream=stream,
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

    def _apply_defaults_and_validate(
        self, search_request: SearchRequest, ctx: Optional["ApiContext"] = None
    ) -> Dict[str, Any]:
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

        # Disable query expansion for keyword-only search
        # Reason: Vespa uses a single sparse embedding for keyword scoring, not per-expanded-query.
        if retrieval_strategy == RetrievalStrategy.KEYWORD and expand_query:
            if ctx:
                ctx.logger.warning(
                    "[SearchFactory] Query expansion disabled for keyword-only search. "
                    "Expansion only benefits neural/hybrid retrieval strategies."
                )
            expand_query = False
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
        return {
            "retrieval_strategy": retrieval_strategy,
            "offset": offset,
            "limit": limit,
            "expand_query": expand_query,
            "interpret_filters": interpret_filters,
            "rerank": rerank,
            "generate_answer": generate_answer,
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

    def _resolve_query_embedder(
        self,
        collection,
        embedder_service: EmbedderServiceProtocol,
        ctx: ApiContext,
    ) -> EmbedderServiceProtocol:
        """Resolve which embedder to use for query embedding.

        If the collection has been synced (embedding_model_name is set), uses
        the collection's stored model. This ensures queries always use the same
        model that produced the stored embeddings, even if the global config
        has since changed.

        Returns:
            The embedder service to use for this query.
        """
        col_model = getattr(collection, "embedding_model_name", None)
        col_dims = getattr(collection, "vector_size", None)

        if col_model is None or col_dims is None:
            # Collection never synced — use global config
            return embedder_service

        if col_model == embedder_service.model_name and col_dims == embedder_service.vector_size:
            # Collection matches global config — reuse cached embedder
            return embedder_service

        # Collection was synced with a different model — build a one-off embedder
        ctx.logger.info(
            f"[SearchFactory] Collection uses model '{col_model}' ({col_dims}d) "
            f"but global config is '{embedder_service.model_name}' "
            f"({embedder_service.vector_size}d). Building query-time embedder."
        )
        return EmbedderService.for_model(
            model=col_model,
            dimensions=col_dims,
            settings=settings,
        )

    async def _emit_skip_notices_if_needed(
        self,
        emitter: EventEmitter,
        has_vector_sources: bool,
        params: Dict[str, Any],
        search_request: SearchRequest,
    ):
        """Emit skip notices for vector-only features when no vector sources exist."""
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
        except Exception:
            raise ValueError("Failed to emit skip notices for vector-only features")

    def _build_operations(
        self,
        params: Dict[str, Any],
        providers: Dict[str, Any],
        federated_sources: List[BaseSource],
        has_vector_sources: bool,
        search_request: SearchRequest,
        vector_size: Optional[int] = None,
        destination: Optional[BaseDestination] = None,
        requires_client_embedding: bool = True,
        db: Optional[AsyncSession] = None,
        ctx: Optional[ApiContext] = None,
        user_principal_override: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        embedder_service: Optional[EmbedderServiceProtocol] = None,
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
            vector_size: Vector dimensions (used by EmbedQuery)
            destination: The destination instance for search (Vespa)
            requires_client_embedding: Whether destination needs client-side embeddings
            db: Database session for access control queries
            ctx: API context with user and organization info
            user_principal_override: If provided, use this user for ACL filtering
                instead of ctx.user. Used for admin "search as user" functionality.
            organization_id: Organization ID for access control queries. Required
                when user_principal_override is provided.
            embedder_service: Embedder service for generating query embeddings
        """
        # Operations that need client-side embeddings
        needs_embedding_ops = has_vector_sources and requires_client_embedding

        # Build access control filter operation if we have user context
        # This resolves the user's access principals and builds the filter
        access_control_op = None

        # Determine the user email for ACL - prefer override, fall back to logged-in user
        acl_user_email = user_principal_override
        if acl_user_email is None and ctx is not None and ctx.user is not None:
            acl_user_email = ctx.user.email

        # Determine organization ID - prefer explicit, fall back to ctx
        acl_org_id = organization_id
        if acl_org_id is None and ctx is not None:
            acl_org_id = ctx.organization.id

        has_acl_context = (
            db is not None
            and acl_user_email is not None
            and acl_org_id is not None
            and has_vector_sources
        )
        if has_acl_context:
            access_control_op = AccessControlFilter(
                db=db,
                user_email=acl_user_email,
                organization_id=acl_org_id,
            )
            if user_principal_override:
                ctx.logger.info(
                    f"[SearchFactory] Created AccessControlFilter for override user: "
                    f"'{user_principal_override}'"
                )

        return {
            "access_control_filter": access_control_op,
            "query_expansion": (
                QueryExpansion(providers=providers["expansion"]) if params["expand_query"] else None
            ),
            # Query interpretation - filters are translated to native format by destination
            "query_interpretation": (
                QueryInterpretation(providers=providers["interpretation"])
                if (params["interpret_filters"] and has_vector_sources)
                else None
            ),
            "embed_query": (
                EmbedQuery(
                    strategy=params["retrieval_strategy"],
                    dense_embedder=embedder_service.get_dense_embedder(),
                    sparse_embedder=embedder_service.get_sparse_embedder(),
                    vector_size=vector_size,
                )
                if (needs_embedding_ops and embedder_service is not None)
                else None
            ),
            # User filter - destination-agnostic (filters are translated by destination)
            "user_filter": (
                UserFilter(filter=search_request.filter)
                if (search_request.filter and has_vector_sources)
                else None
            ),
            # Unified retrieval operation (destination-agnostic)
            "retrieval": (
                Retrieval(
                    destination=destination,
                    strategy=params["retrieval_strategy"],
                    offset=params["offset"],
                    limit=params["limit"],
                )
                if (has_vector_sources and destination)
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
            f"limit={params['limit']}, \n"
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
            "mistral": getattr(settings, "MISTRAL_API_KEY", None),
        }

    def _create_provider_for_each_operation(
        self,
        api_keys: Dict[str, Optional[str]],
        params: Dict[str, Any],
        has_federated_sources: bool,
        has_vector_sources: bool,
        ctx: ApiContext,
        requires_client_embedding: bool = True,
    ) -> Dict[str, BaseProvider]:
        """Select and validate all required LLM providers.

        Note: Embedding is handled by the domain embedder service, not providers.
        """
        providers = {}

        # Create LLM providers for enabled operations
        providers.update(
            self._create_llm_providers(
                api_keys,
                params,
                has_federated_sources,
                has_vector_sources,
                ctx,
                requires_client_embedding=requires_client_embedding,
            )
        )

        ctx.logger.debug(f"[SearchFactory] Providers: {providers}")
        return providers

    def _create_llm_providers(
        self,
        api_keys: Dict[str, Optional[str]],
        params: Dict[str, Any],
        has_federated_sources: bool,
        has_vector_sources: bool,
        ctx: ApiContext,
        requires_client_embedding: bool = True,
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

        # Query interpretation - destination-agnostic (filters are translated to native format)
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
                if not getattr(source_class, "federated_search", False):
                    return True
            return False
        except Exception:
            raise ValueError(
                f"Error getting vector sources for collection {collection.readable_id}"
            )

    async def _resolve_destination(
        self,
        db: AsyncSession,
        collection,
        ctx: ApiContext,
        destination_override: Optional[DestinationOverride] = None,
    ) -> BaseDestination:
        """Resolve the destination for search.

        If destination_override is provided, creates that specific destination.
        Otherwise, uses collection's default destination (Vespa).

        Args:
            db: Database session
            collection: Collection object
            ctx: API context
            destination_override: Override destination ("vespa")

        Returns:
            Destination instance (Vespa)
        """
        if destination_override == "vespa":
            from airweave.platform.destinations.vespa import VespaDestination

            ctx.logger.info(
                f"[SearchFactory] Using Vespa destination (override) for "
                f"collection {collection.readable_id}"
            )
            return await VespaDestination.create(
                collection_id=collection.id,
                organization_id=collection.organization_id,
                logger=ctx.logger,
            )
        else:
            # No override - use default destination resolution
            return await self._get_destination_for_collection(db, collection, ctx)

    async def _get_destination_for_collection(
        self, db: AsyncSession, collection, ctx: ApiContext
    ) -> BaseDestination:
        """Get the default destination instance for a collection.

        Uses Vespa as the sole vector database destination.
        """
        from airweave.platform.destinations.vespa import VespaDestination

        ctx.logger.info(f"[SearchFactory] Collection {collection.readable_id} uses Vespa")
        return await VespaDestination.create(
            collection_id=collection.id,
            organization_id=collection.organization_id,
            logger=ctx.logger,
        )

    def _init_all_providers_for_operation(  # noqa: C901
        self,
        operation_name: str,
        api_keys: Dict[str, Optional[str]],
        ctx: ApiContext,
    ) -> List[BaseProvider]:
        """Initialize ALL available providers for an operation in preference order.

        Returns list of working providers that can be used for fallback.
        Operations will try providers in order until one succeeds.

        Note: Embedding is handled by the domain embedder service, not providers.

        Args:
            operation_name: Name of the operation (e.g., "query_expansion")
            api_keys: Dict of provider API keys
            ctx: API context
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
            embedding_config = self._build_embedding_config(provider_spec, entry.get("embedding"))
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
                elif provider_name == "mistral":
                    ctx.logger.debug(
                        f"[Factory] Attempting to initialize MistralProvider for {operation_name}"
                    )
                    provider = MistralProvider(api_key=api_key, model_spec=model_spec, ctx=ctx)
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
                source_instance = await self._instantiate_federated_source(
                    db, source_connection, ctx
                )
                if source_instance:
                    federated_sources.append(source_instance)

            return federated_sources

        except Exception as e:
            raise ValueError(f"Error getting federated sources: {e}")

    # [code blue] replace with SourceLifecycleService.create()
    async def _instantiate_federated_source(
        self, db: AsyncSession, source_connection, ctx: ApiContext
    ) -> Optional[BaseSource]:
        """Instantiate federated source - mirrors sync factory pattern.

        Follows the same clean architecture as sync factory's _create_source_instance_with_data
        for consistent auth provider, proxy, and token manager support.

        Returns:
            BaseSource instance if source supports federated search, None if not federated

        Raises:
            ValueError: If source is federated but instantiation fails
        """
        # Step 1: Get source model and validate federated search capability
        source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
        if not source_model:
            ctx.logger.warning(f"Source model not found for {source_connection.short_name}")
            return None

        source_class = resource_locator.get_source(source_model)
        if not getattr(source_class, "federated_search", False):
            return None

        # From here, source IS federated - any error should fail the search
        ctx.logger.info(
            f"Found federated source: {source_connection.short_name} (id: {source_connection.id})"
        )

        try:
            # Step 2: Build source_connection_data dict
            source_connection_data = {
                "source_model": source_model,
                "source_class": source_class,
                "short_name": source_connection.short_name,
                "config_fields": source_connection.config_fields,
                "readable_auth_provider_id": getattr(
                    source_connection, "readable_auth_provider_id", None
                ),
                "auth_provider_config": getattr(source_connection, "auth_provider_config", None),
                "connection_id": getattr(source_connection, "connection_id", None),
                "integration_credential_id": None,  # Loaded below
                "auth_config_class": None,  # Not used for federated search
            }

            # Load integration_credential_id from connection if exists
            if source_connection_data["connection_id"]:
                connection = await crud.connection.get(
                    db, source_connection_data["connection_id"], ctx
                )
                if connection:
                    source_connection_data["integration_credential_id"] = (
                        connection.integration_credential_id
                    )

            # Step 3: Get complete auth configuration (shared utility)
            auth_config = await get_auth_configuration(
                db=db,
                source_connection_data=source_connection_data,
                ctx=ctx,
                logger=ctx.logger,
                access_token=None,  # Search never uses direct injection
            )

            # Step 4: Process credentials for source consumption (shared utility)
            source_credentials = await process_credentials_for_source(
                raw_credentials=auth_config["credentials"],
                source_connection_data=source_connection_data,
                logger=ctx.logger,
            )

            # Step 5: Create source instance
            source_instance = await source_class.create(
                source_credentials, config=source_connection_data["config_fields"]
            )

            # Step 6: Set logger
            if hasattr(source_instance, "set_logger"):
                source_instance.set_logger(ctx.logger)

            # Step 7: Set HTTP client factory for proxy mode
            if auth_config.get("http_client_factory"):
                ctx.logger.info(f"Proxy mode active for {source_connection.short_name}")
                source_instance.set_http_client_factory(auth_config["http_client_factory"])

            # Step 8: Wrap HTTP client with AirweaveHttpClient for rate limiting
            # This ensures federated sources respect rate limits just like sync sources
            from airweave.platform.utils.source_factory_utils import (
                wrap_source_with_airweave_client,
            )

            wrap_source_with_airweave_client(
                source=source_instance,
                source_short_name=source_connection.short_name,
                source_connection_id=source_connection.id,
                ctx=ctx,
                logger=ctx.logger,
            )

            # Store source connection ID on instance for error tracking
            source_instance._source_connection_id = str(source_connection.id)

            # Step 9: Setup token manager for OAuth sources that support refresh
            self._maybe_setup_token_manager(
                source_instance,
                source_model,
                db,
                source_connection,
                source_connection_data,
                auth_config,
                ctx,
            )

            ctx.logger.info(
                f"Successfully instantiated federated source: {source_connection.short_name}"
            )
            return source_instance

        except Exception as e:
            ctx.logger.error(
                f"Failed to instantiate federated source {source_connection.short_name}: {e}",
                exc_info=True,
            )
            # Re-raise to fail the search - federated sources must work or search should fail
            raise ValueError(
                f"Failed to instantiate federated source '{source_connection.short_name}'. "
                f"This source is configured for your collection but cannot be searched. "
                f"Error: {str(e)}"
            ) from e

    def _maybe_setup_token_manager(
        self,
        source_instance: BaseSource,
        source_model,
        db: AsyncSession,
        source_connection,
        source_connection_data: dict,
        auth_config: dict,
        ctx: ApiContext,
    ) -> None:
        """Setup token manager if source requires it, skip for proxy mode."""
        from airweave.platform.auth_providers.auth_result import AuthProviderMode
        from airweave.schemas.source_connection import OAuthType

        auth_mode = auth_config.get("auth_mode")
        is_proxy_mode = auth_mode == AuthProviderMode.PROXY

        if is_proxy_mode:
            ctx.logger.info(
                f"⏭️ Skipping token manager for {source_connection.short_name} - "
                f"proxy mode (proxy client manages tokens internally)"
            )
            return

        if not source_model.oauth_type:
            return

        # Only create token manager for sources with refresh capability
        if source_model.oauth_type not in (OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH):
            ctx.logger.debug(
                f"⏭️ Skipping token manager for {source_connection.short_name} - "
                f"oauth_type={source_model.oauth_type} does not support token refresh"
            )
            return

        self._setup_token_manager(
            source_instance,
            db,
            source_connection,
            source_connection_data.get("integration_credential_id"),
            auth_config["credentials"],
            ctx,
            auth_provider_instance=auth_config.get("auth_provider_instance"),
        )

    def _setup_token_manager(
        self,
        source_instance: BaseSource,
        db: AsyncSession,
        source_connection,
        integration_credential_id: Optional[UUID],
        decrypted_credential: dict,
        ctx: ApiContext,
        auth_provider_instance=None,
    ):
        """Setup token manager for OAuth sources with auth provider support."""
        minimal_connection = type(
            "MinimalConnection",
            (),
            {
                "id": source_connection.connection_id,
                "integration_credential_id": integration_credential_id,
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
            auth_provider_instance=auth_provider_instance,
        )
        source_instance.set_token_manager(token_manager)


factory = SearchFactory()
