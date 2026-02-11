"""Services container for agentic search.

This is the composition root - where external dependencies are wired together.
"""

from __future__ import annotations

from airweave.adapters.circuit_breaker import InMemoryCircuitBreaker
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.search.agentic_search.config import (
    DatabaseImpl,
    DenseEmbedderProvider,
    LLMModel,
    LLMProvider,
    SparseEmbedderProvider,
    TokenizerType,
    VectorDBProvider,
    config,
)
from airweave.search.agentic_search.external.database import AgenticSearchDatabaseInterface
from airweave.search.agentic_search.external.dense_embedder import (
    AgenticSearchDenseEmbedderInterface,
)
from airweave.search.agentic_search.external.dense_embedder.registry import (
    get_model_spec as get_dense_model_spec,
)
from airweave.search.agentic_search.external.dense_embedder.registry import validate_vector_size
from airweave.search.agentic_search.external.llm import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.llm.registry import (
    FALLBACK_CHAIN,
    LLMModelSpec,
    resolve_provider_for_model,
)
from airweave.search.agentic_search.external.llm.registry import (
    get_model_spec as get_llm_model_spec,
)
from airweave.search.agentic_search.external.sparse_embedder import (
    AgenticSearchSparseEmbedderInterface,
)
from airweave.search.agentic_search.external.sparse_embedder.registry import (
    get_model_spec as get_sparse_model_spec,
)
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface
from airweave.search.agentic_search.external.tokenizer.registry import (
    get_model_spec as get_tokenizer_model_spec,
)
from airweave.search.agentic_search.external.vector_database import AgenticSearchVectorDBInterface

# Module-level singletons shared across all requests
_shared_circuit_breaker: InMemoryCircuitBreaker | None = None
_shared_llm_cache: dict[LLMModel, AgenticSearchLLMInterface] = {}


def _get_shared_circuit_breaker() -> InMemoryCircuitBreaker:
    """Get the shared circuit breaker, creating it on first use."""
    global _shared_circuit_breaker
    if _shared_circuit_breaker is None:
        _shared_circuit_breaker = InMemoryCircuitBreaker()
    return _shared_circuit_breaker


class AgenticSearchServices:
    """Container for external dependencies.

    This is the composition root - where external dependencies are wired together.
    Components use these services:
    - services.db for metadata queries
    - services.tokenizer.count_tokens() for token counting
    - services.llm.model_spec for context limits
    - services.llm.structured_output() for LLM calls
    - services.dense_embedder.embed_batch() for semantic embeddings
    - services.sparse_embedder.embed() for keyword embeddings
    - services.vector_db.compile_query() and execute_query() for search
    """

    def __init__(
        self,
        db: AgenticSearchDatabaseInterface,
        tokenizer: AgenticSearchTokenizerInterface,
        llm: AgenticSearchLLMInterface,
        dense_embedder: AgenticSearchDenseEmbedderInterface,
        sparse_embedder: AgenticSearchSparseEmbedderInterface,
        vector_db: AgenticSearchVectorDBInterface,
    ):
        """Initialize with external dependencies.

        Args:
            db: Database interface for metadata queries.
            tokenizer: Tokenizer interface for token counting.
            llm: LLM interface for structured output.
            dense_embedder: Dense embedder for semantic search.
            sparse_embedder: Sparse embedder for keyword search.
            vector_db: Vector database for query compilation and execution.
        """
        self.db = db
        self.tokenizer = tokenizer
        self.llm = llm
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.vector_db = vector_db

    @classmethod
    async def create(
        cls,
        ctx: ApiContext,
        readable_id: str,
        model: LLMModel,
    ) -> AgenticSearchServices:
        """Create services based on config and the requested model.

        The LLM provider is resolved automatically from the model via the registry.

        Args:
            ctx: API context for organization scoping and logging.
            readable_id: Collection readable ID (used to get vector_size for embedders).
            model: LLM model to use (determines the provider automatically).

        Returns:
            AgenticSearchServices instance with all dependencies wired.
        """
        llm_provider = resolve_provider_for_model(model)

        db = await cls._create_db(ctx)

        tokenizer = cls._create_tokenizer(model, llm_provider)
        llm = cls._create_llm(tokenizer, model, llm_provider)

        vector_size = await db.get_collection_vector_size(readable_id)
        dense_embedder = cls._create_dense_embedder(vector_size)
        sparse_embedder = cls._create_sparse_embedder()

        vector_db = await cls._create_vector_db(ctx)

        # Log initialized services summary
        llm_spec = llm.model_spec
        tokenizer_spec = tokenizer.model_spec
        dense_spec = dense_embedder.model_spec
        sparse_spec = sparse_embedder.model_spec

        ctx.logger.debug(
            f"[AgenticSearchServices] Initialized:\n"
            f"  - Database: {config.DATABASE_IMPL.value}\n"
            f"  - LLM: {llm_provider.value} / {llm_spec.api_model_name}\n"
            f"  - Tokenizer: {config.TOKENIZER_TYPE.value} / "
            f"{tokenizer_spec.encoding_name}\n"
            f"  - Dense embedder: {config.DENSE_EMBEDDER_PROVIDER.value} / "
            f"{dense_spec.api_model_name} (vector_size={vector_size})\n"
            f"  - Sparse embedder: {config.SPARSE_EMBEDDER_PROVIDER.value} / "
            f"{sparse_spec.model_name}\n"
            f"  - Vector DB: {config.VECTOR_DB_PROVIDER.value}"
        )

        return cls(
            db=db,
            tokenizer=tokenizer,
            llm=llm,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            vector_db=vector_db,
        )

    @staticmethod
    async def _create_db(ctx: ApiContext) -> AgenticSearchDatabaseInterface:
        """Create database based on config.

        Args:
            ctx: API context for logging and organization scoping.

        Returns:
            Database interface implementation.

        Raises:
            ValueError: If database implementation is unknown.
        """
        if config.DATABASE_IMPL == DatabaseImpl.POSTGRESQL:
            from airweave.search.agentic_search.external.database.postgresql import (
                PostgreSQLAgenticSearchDatabase,
            )

            return await PostgreSQLAgenticSearchDatabase.create(ctx)

        raise ValueError(f"Unknown database implementation: {config.DATABASE_IMPL}")

    @staticmethod
    def _create_tokenizer(
        llm_model: LLMModel,
        llm_provider: LLMProvider,
    ) -> AgenticSearchTokenizerInterface:
        """Create tokenizer based on config.

        Gets the model spec from the registry and validates that the
        tokenizer is compatible with the chosen LLM model.

        Args:
            llm_model: The LLM model to validate tokenizer compatibility against.
            llm_provider: The resolved LLM provider for registry lookup.

        Returns:
            Tokenizer interface implementation.

        Raises:
            ValueError: If tokenizer type or encoding is unknown.
            ValueError: If tokenizer doesn't match LLM requirements.
        """
        # Get tokenizer spec
        model_spec = get_tokenizer_model_spec(
            config.TOKENIZER_TYPE,
            config.TOKENIZER_ENCODING,
        )

        # Validate compatibility with LLM
        llm_spec = get_llm_model_spec(llm_provider, llm_model)
        if config.TOKENIZER_TYPE != llm_spec.required_tokenizer_type:
            raise ValueError(
                f"LLM '{llm_model.value}' requires tokenizer type "
                f"'{llm_spec.required_tokenizer_type.value}', "
                f"but config specifies '{config.TOKENIZER_TYPE.value}'"
            )
        if config.TOKENIZER_ENCODING != llm_spec.required_tokenizer_encoding:
            raise ValueError(
                f"LLM '{llm_model.value}' requires tokenizer encoding "
                f"'{llm_spec.required_tokenizer_encoding.value}', "
                f"but config specifies '{config.TOKENIZER_ENCODING.value}'"
            )

        if config.TOKENIZER_TYPE == TokenizerType.TIKTOKEN:
            from airweave.search.agentic_search.external.tokenizer.tiktoken import (
                TiktokenTokenizer,
            )

            return TiktokenTokenizer(model_spec=model_spec)

        raise ValueError(f"Unknown tokenizer type: {config.TOKENIZER_TYPE}")

    @staticmethod
    def _create_single_provider(
        provider: LLMProvider,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
    ) -> AgenticSearchLLMInterface:
        """Create a single LLM provider instance.

        Providers use the module-level logger so they can be long-lived singletons.

        Args:
            provider: The LLM provider enum.
            model_spec: Model specification for this provider.
            tokenizer: Shared tokenizer.

        Returns:
            LLM interface implementation.

        Raises:
            ValueError: If provider is unknown.
        """
        if provider == LLMProvider.CEREBRAS:
            from airweave.search.agentic_search.external.llm.cerebras import CerebrasLLM

            return CerebrasLLM(model_spec=model_spec, tokenizer=tokenizer)

        if provider == LLMProvider.GROQ:
            from airweave.search.agentic_search.external.llm.groq import GroqLLM

            return GroqLLM(model_spec=model_spec, tokenizer=tokenizer)

        if provider == LLMProvider.ANTHROPIC:
            from airweave.search.agentic_search.external.llm.anthropic import AnthropicLLM

            return AnthropicLLM(model_spec=model_spec, tokenizer=tokenizer)

        raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def _create_llm(
        tokenizer: AgenticSearchTokenizerInterface,
        llm_model: LLMModel,
        llm_provider: LLMProvider,
    ) -> AgenticSearchLLMInterface:
        """Get or create a shared LLM with automatic fallback chain.

        The LLM chain is cached per model and reused across all requests.
        This ensures the circuit breaker state (which providers are tripped)
        persists and the SDK clients are reused.

        Builds a chain of providers: primary → Groq → Anthropic.
        Fallback providers are only added if their API key is configured.

        Args:
            tokenizer: Tokenizer for accurate token counting.
            llm_model: The LLM model to use.
            llm_provider: The resolved LLM provider for this model.

        Returns:
            Shared LLM interface implementation (possibly wrapped in FallbackChainLLM).

        Raises:
            ValueError: If LLM provider is unknown.
        """
        # Return cached chain if already built for this model
        if llm_model in _shared_llm_cache:
            return _shared_llm_cache[llm_model]

        from airweave.core.logging import logger

        model_spec = get_llm_model_spec(llm_provider, llm_model)

        # Build the primary provider
        primary = AgenticSearchServices._create_single_provider(llm_provider, model_spec, tokenizer)

        # Build fallback chain from registry
        chain: list[AgenticSearchLLMInterface] = [primary]

        for fb in FALLBACK_CHAIN:
            if fb.provider == llm_provider:
                continue

            api_key = getattr(settings, fb.api_key_setting, None)
            if not api_key:
                continue

            try:
                fb_instance = AgenticSearchServices._create_single_provider(
                    fb.provider, fb.model_spec, tokenizer
                )
                chain.append(fb_instance)
                logger.info(
                    f"[AgenticSearchServices] {fb.provider.value} fallback enabled "
                    f"({fb.model_spec.api_model_name})"
                )
            except Exception as e:
                logger.warning(
                    f"[AgenticSearchServices] Failed to initialize "
                    f"{fb.provider.value} fallback: {e}. Skipping."
                )

        # If we have multiple providers, wrap in FallbackChainLLM with circuit breaker
        if len(chain) > 1:
            from airweave.search.agentic_search.external.llm.fallback import FallbackChainLLM

            result: AgenticSearchLLMInterface = FallbackChainLLM(
                providers=chain,
                circuit_breaker=_get_shared_circuit_breaker(),
            )
        else:
            result = primary

        _shared_llm_cache[llm_model] = result
        return result

    @staticmethod
    def _create_dense_embedder(vector_size: int) -> AgenticSearchDenseEmbedderInterface:
        """Create dense embedder based on config.

        Gets the model spec from the registry and validates that it supports
        the collection's vector_size.

        Args:
            vector_size: Embedding dimension for the collection.

        Returns:
            Dense embedder interface implementation.

        Raises:
            ValueError: If dense embedder provider or model is unknown.
            ValueError: If vector_size exceeds model's maximum.
        """
        model_spec = get_dense_model_spec(
            config.DENSE_EMBEDDER_PROVIDER,
            config.DENSE_EMBEDDER_MODEL,
        )
        validate_vector_size(model_spec, vector_size)

        if config.DENSE_EMBEDDER_PROVIDER == DenseEmbedderProvider.OPENAI:
            from airweave.search.agentic_search.external.dense_embedder.openai import (
                OpenAIDenseEmbedder,
            )

            return OpenAIDenseEmbedder(model_spec=model_spec, vector_size=vector_size)

        raise ValueError(f"Unknown dense embedder provider: {config.DENSE_EMBEDDER_PROVIDER}")

    @staticmethod
    def _create_sparse_embedder() -> AgenticSearchSparseEmbedderInterface:
        """Create sparse embedder based on config.

        Gets the model spec from the registry.

        Returns:
            Sparse embedder interface implementation.

        Raises:
            ValueError: If sparse embedder provider or model is unknown.
        """
        model_spec = get_sparse_model_spec(
            config.SPARSE_EMBEDDER_PROVIDER,
            config.SPARSE_EMBEDDER_MODEL,
        )

        if config.SPARSE_EMBEDDER_PROVIDER == SparseEmbedderProvider.FASTEMBED:
            from airweave.search.agentic_search.external.sparse_embedder.fastembed import (
                FastEmbedSparseEmbedder,
            )

            return FastEmbedSparseEmbedder(model_spec=model_spec)

        raise ValueError(f"Unknown sparse embedder provider: {config.SPARSE_EMBEDDER_PROVIDER}")

    @staticmethod
    async def _create_vector_db(ctx: ApiContext) -> AgenticSearchVectorDBInterface:
        """Create vector database based on config.

        Args:
            ctx: API context for logging.

        Returns:
            Vector database interface implementation.

        Raises:
            ValueError: If vector DB provider is unknown.
        """
        if config.VECTOR_DB_PROVIDER == VectorDBProvider.VESPA:
            from airweave.search.agentic_search.external.vector_database.vespa import (
                VespaVectorDB,
            )

            return await VespaVectorDB.create(ctx)

        raise ValueError(f"Unknown vector DB provider: {config.VECTOR_DB_PROVIDER}")

    async def close(self) -> None:
        """Clean up per-request resources.

        Note: LLM is a shared singleton and is NOT closed here.
        It persists across requests for circuit breaker continuity.
        """
        await self.db.close()
        await self.dense_embedder.close()
        await self.sparse_embedder.close()
        await self.vector_db.close()
