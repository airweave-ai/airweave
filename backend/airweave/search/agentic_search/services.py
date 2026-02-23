"""Services container for agentic search.

This is the composition root - where external dependencies are wired together.
"""

from __future__ import annotations

from airweave.adapters.circuit_breaker import InMemoryCircuitBreaker
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.domains.embedders.protocols import (
    DenseEmbedderProtocol,
    EmbedderServiceProtocol,
    SparseEmbedderProtocol,
)
from airweave.search.agentic_search.config import (
    DatabaseImpl,
    LLMProvider,
    TokenizerType,
    VectorDBProvider,
    config,
)
from airweave.search.agentic_search.external.database import AgenticSearchDatabaseInterface
from airweave.search.agentic_search.external.llm import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.llm.registry import (
    PROVIDER_API_KEY_SETTINGS,
    LLMModelSpec,
)
from airweave.search.agentic_search.external.llm.registry import (
    get_model_spec as get_llm_model_spec,
)
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface
from airweave.search.agentic_search.external.tokenizer.registry import (
    get_model_spec as get_tokenizer_model_spec,
)
from airweave.search.agentic_search.external.vector_database import AgenticSearchVectorDBInterface

# Module-level singletons shared across all requests
_shared_circuit_breaker: InMemoryCircuitBreaker | None = None
_shared_llm: AgenticSearchLLMInterface | None = None


def _get_shared_circuit_breaker() -> InMemoryCircuitBreaker:
    """Get the shared circuit breaker, creating it on first use."""
    global _shared_circuit_breaker
    if _shared_circuit_breaker is None:
        _shared_circuit_breaker = InMemoryCircuitBreaker()
    return _shared_circuit_breaker


class AgenticSearchServices:
    """Container for external dependencies.

    Components use these services:
    - services.db for metadata queries
    - services.tokenizer.count_tokens() for token counting
    - services.llm.model_spec for context limits
    - services.llm.structured_output() for LLM calls
    - services.dense_embedder.embed_many() for semantic embeddings
    - services.sparse_embedder.embed() for keyword embeddings
    - services.vector_db.compile_query() and execute_query() for search
    """

    def __init__(
        self,
        db: AgenticSearchDatabaseInterface,
        tokenizer: AgenticSearchTokenizerInterface,
        llm: AgenticSearchLLMInterface,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        vector_db: AgenticSearchVectorDBInterface,
    ):
        """Initialize agentic search service with dependencies."""
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
        embedder_service: EmbedderServiceProtocol,
    ) -> AgenticSearchServices:
        """Create services from config.

        Args:
            ctx: API context for organization scoping and logging.
            readable_id: Collection readable ID.
            embedder_service: Domain embedder service (from container).

        Returns:
            AgenticSearchServices instance with all dependencies wired.
        """
        db = await cls._create_db(ctx)

        tokenizer = cls._create_tokenizer()
        llm = cls._create_llm(tokenizer)

        dense_embedder = embedder_service.get_dense_embedder()
        sparse_embedder = embedder_service.get_sparse_embedder()

        vector_db = await cls._create_vector_db(ctx)

        # Log initialized services summary
        llm_spec = llm.model_spec
        tokenizer_spec = tokenizer.model_spec

        chain_desc = " → ".join(f"{p.value}/{m.value}" for p, m in config.LLM_FALLBACK_CHAIN)
        ctx.logger.debug(
            f"[AgenticSearchServices] Initialized:\n"
            f"  - Database: {config.DATABASE_IMPL.value}\n"
            f"  - LLM chain: {chain_desc}\n"
            f"  - Primary LLM: {llm_spec.api_model_name}\n"
            f"  - Tokenizer: {config.TOKENIZER_TYPE.value} / "
            f"{tokenizer_spec.encoding_name}\n"
            f"  - Embedder: vector_size={embedder_service.vector_size}\n"
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
        if config.DATABASE_IMPL == DatabaseImpl.POSTGRESQL:
            from airweave.search.agentic_search.external.database.postgresql import (
                PostgreSQLAgenticSearchDatabase,
            )

            return await PostgreSQLAgenticSearchDatabase.create(ctx)

        raise ValueError(f"Unknown database implementation: {config.DATABASE_IMPL}")

    @staticmethod
    def _create_tokenizer() -> AgenticSearchTokenizerInterface:
        if not config.LLM_FALLBACK_CHAIN:
            raise ValueError("LLM_FALLBACK_CHAIN is empty — at least one provider is required")

        primary_provider, primary_model = config.LLM_FALLBACK_CHAIN[0]
        llm_spec = get_llm_model_spec(primary_provider, primary_model)

        if config.TOKENIZER_TYPE != llm_spec.required_tokenizer_type:
            raise ValueError(
                f"Primary LLM '{primary_provider.value}/{primary_model.value}' requires "
                f"tokenizer type '{llm_spec.required_tokenizer_type.value}', "
                f"but config specifies '{config.TOKENIZER_TYPE.value}'"
            )
        if config.TOKENIZER_ENCODING != llm_spec.required_tokenizer_encoding:
            raise ValueError(
                f"Primary LLM '{primary_provider.value}/{primary_model.value}' requires "
                f"tokenizer encoding '{llm_spec.required_tokenizer_encoding.value}', "
                f"but config specifies '{config.TOKENIZER_ENCODING.value}'"
            )

        model_spec = get_tokenizer_model_spec(
            config.TOKENIZER_TYPE,
            config.TOKENIZER_ENCODING,
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
    ) -> AgenticSearchLLMInterface:
        global _shared_llm
        if _shared_llm is not None:
            return _shared_llm

        from airweave.core.logging import logger

        chain: list[AgenticSearchLLMInterface] = []

        for provider, model in config.LLM_FALLBACK_CHAIN:
            api_key_attr = PROVIDER_API_KEY_SETTINGS.get(provider)
            if api_key_attr:
                api_key = getattr(settings, api_key_attr, None)
                if not api_key:
                    logger.debug(
                        f"[AgenticSearchServices] Skipping {provider.value}/{model.value} "
                        f"(no {api_key_attr})"
                    )
                    continue

            model_spec = get_llm_model_spec(provider, model)

            try:
                instance = AgenticSearchServices._create_single_provider(
                    provider, model_spec, tokenizer
                )
                chain.append(instance)
                logger.info(
                    f"[AgenticSearchServices] LLM provider ready: "
                    f"{provider.value}/{model.value} ({model_spec.api_model_name})"
                )
            except Exception as e:
                logger.warning(
                    f"[AgenticSearchServices] Failed to initialize "
                    f"{provider.value}/{model.value}: {e}. Skipping."
                )

        if not chain:
            raise ValueError(
                "No LLM providers could be initialized. Check API keys and "
                "config.LLM_FALLBACK_CHAIN."
            )

        if len(chain) > 1:
            from airweave.search.agentic_search.external.llm.fallback import FallbackChainLLM

            result: AgenticSearchLLMInterface = FallbackChainLLM(
                providers=chain,
                circuit_breaker=_get_shared_circuit_breaker(),
            )
        else:
            result = chain[0]

        _shared_llm = result
        return result

    @staticmethod
    async def _create_vector_db(ctx: ApiContext) -> AgenticSearchVectorDBInterface:
        if config.VECTOR_DB_PROVIDER == VectorDBProvider.VESPA:
            from airweave.search.agentic_search.external.vector_database.vespa import (
                VespaVectorDB,
            )

            return await VespaVectorDB.create(ctx)

        raise ValueError(f"Unknown vector DB provider: {config.VECTOR_DB_PROVIDER}")

    async def close(self) -> None:
        """Clean up per-request resources."""
        await self.db.close()
        await self.dense_embedder.close()
        await self.sparse_embedder.close()
        await self.vector_db.close()
