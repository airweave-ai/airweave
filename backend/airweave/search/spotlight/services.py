"""Services container for spotlight search.

This is the composition root - where external dependencies are wired together.
"""

from __future__ import annotations

from airweave.api.context import ApiContext
from airweave.search.spotlight.config import (
    DatabaseImpl,
    DenseEmbedderProvider,
    LLMProvider,
    SparseEmbedderProvider,
    TokenizerType,
    VectorDBProvider,
    config,
)
from airweave.search.spotlight.external.database import SpotlightDatabaseInterface
from airweave.search.spotlight.external.dense_embedder import SpotlightDenseEmbedderInterface
from airweave.search.spotlight.external.dense_embedder.registry import (
    get_model_spec as get_dense_model_spec,
)
from airweave.search.spotlight.external.dense_embedder.registry import validate_vector_size
from airweave.search.spotlight.external.llm import SpotlightLLMInterface
from airweave.search.spotlight.external.llm.registry import (
    get_model_spec as get_llm_model_spec,
)
from airweave.search.spotlight.external.sparse_embedder import SpotlightSparseEmbedderInterface
from airweave.search.spotlight.external.sparse_embedder.registry import (
    get_model_spec as get_sparse_model_spec,
)
from airweave.search.spotlight.external.tokenizer import SpotlightTokenizerInterface
from airweave.search.spotlight.external.tokenizer.registry import (
    get_model_spec as get_tokenizer_model_spec,
)
from airweave.search.spotlight.external.vector_database import SpotlightVectorDBInterface


class SpotlightServices:
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
        db: SpotlightDatabaseInterface,
        tokenizer: SpotlightTokenizerInterface,
        llm: SpotlightLLMInterface,
        dense_embedder: SpotlightDenseEmbedderInterface,
        sparse_embedder: SpotlightSparseEmbedderInterface,
        vector_db: SpotlightVectorDBInterface,
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
    async def create(cls, ctx: ApiContext, readable_id: str) -> SpotlightServices:
        """Create services based on config.

        Args:
            ctx: API context for organization scoping and logging.
            readable_id: Collection readable ID (used to get vector_size for embedders).

        Returns:
            SpotlightServices instance with all dependencies wired.
        """
        db = await cls._create_db(ctx)

        tokenizer = cls._create_tokenizer()
        llm = cls._create_llm(ctx, tokenizer)

        vector_size = await db.get_collection_vector_size(readable_id)
        dense_embedder = cls._create_dense_embedder(vector_size)
        sparse_embedder = cls._create_sparse_embedder()

        vector_db = await cls._create_vector_db(ctx)

        # Log initialized services summary
        llm_spec = llm.model_spec
        tokenizer_spec = tokenizer.model_spec
        dense_spec = dense_embedder.model_spec
        sparse_spec = sparse_embedder.model_spec

        ctx.logger.info(
            f"[SpotlightServices] Initialized:\n"
            f"  - Database: {config.DATABASE_IMPL.value}\n"
            f"  - LLM: {config.LLM_PROVIDER.value} / {llm_spec.api_model_name}\n"
            f"  - Tokenizer: {config.TOKENIZER_TYPE.value} / {tokenizer_spec.encoding_name}\n"
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
    async def _create_db(ctx: ApiContext) -> SpotlightDatabaseInterface:
        """Create database based on config.

        Args:
            ctx: API context for logging and organization scoping.

        Returns:
            Database interface implementation.

        Raises:
            ValueError: If database implementation is unknown.
        """
        if config.DATABASE_IMPL == DatabaseImpl.POSTGRESQL:
            from airweave.search.spotlight.external.database.postgresql import (
                PostgreSQLSpotlightDatabase,
            )

            return await PostgreSQLSpotlightDatabase.create(ctx)

        raise ValueError(f"Unknown database implementation: {config.DATABASE_IMPL}")

    @staticmethod
    def _create_tokenizer() -> SpotlightTokenizerInterface:
        """Create tokenizer based on config.

        Gets the model spec from the registry and validates that the
        tokenizer is compatible with the configured LLM.

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
        llm_spec = get_llm_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)
        if config.TOKENIZER_TYPE != llm_spec.required_tokenizer_type:
            raise ValueError(
                f"LLM '{config.LLM_MODEL.value}' requires tokenizer type "
                f"'{llm_spec.required_tokenizer_type.value}', "
                f"but config specifies '{config.TOKENIZER_TYPE.value}'"
            )
        if config.TOKENIZER_ENCODING != llm_spec.required_tokenizer_encoding:
            raise ValueError(
                f"LLM '{config.LLM_MODEL.value}' requires tokenizer encoding "
                f"'{llm_spec.required_tokenizer_encoding.value}', "
                f"but config specifies '{config.TOKENIZER_ENCODING.value}'"
            )

        if config.TOKENIZER_TYPE == TokenizerType.TIKTOKEN:
            from airweave.search.spotlight.external.tokenizer.tiktoken import (
                TiktokenTokenizer,
            )

            return TiktokenTokenizer(model_spec=model_spec)

        raise ValueError(f"Unknown tokenizer type: {config.TOKENIZER_TYPE}")

    @staticmethod
    def _create_llm(
        ctx: ApiContext,
        tokenizer: SpotlightTokenizerInterface,
    ) -> SpotlightLLMInterface:
        """Create LLM based on config.

        Gets the model spec from the registry.

        Args:
            ctx: API context for logging.
            tokenizer: Tokenizer for accurate token counting in rate limiting.

        Returns:
            LLM interface implementation.

        Raises:
            ValueError: If LLM provider is unknown.
        """
        model_spec = get_llm_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)

        if config.LLM_PROVIDER == LLMProvider.CEREBRAS:
            from airweave.search.spotlight.external.llm.cerebras import CerebrasLLM

            return CerebrasLLM(
                model_spec=model_spec,
                tokenizer=tokenizer,
                logger=ctx.logger,
            )

        raise ValueError(f"Unknown LLM provider: {config.LLM_PROVIDER}")

    @staticmethod
    def _create_dense_embedder(vector_size: int) -> SpotlightDenseEmbedderInterface:
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
            from airweave.search.spotlight.external.dense_embedder.openai import (
                OpenAIDenseEmbedder,
            )

            return OpenAIDenseEmbedder(model_spec=model_spec, vector_size=vector_size)

        raise ValueError(f"Unknown dense embedder provider: {config.DENSE_EMBEDDER_PROVIDER}")

    @staticmethod
    def _create_sparse_embedder() -> SpotlightSparseEmbedderInterface:
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
            from airweave.search.spotlight.external.sparse_embedder.fastembed import (
                FastEmbedSparseEmbedder,
            )

            return FastEmbedSparseEmbedder(model_spec=model_spec)

        raise ValueError(f"Unknown sparse embedder provider: {config.SPARSE_EMBEDDER_PROVIDER}")

    @staticmethod
    async def _create_vector_db(ctx: ApiContext) -> SpotlightVectorDBInterface:
        """Create vector database based on config.

        Args:
            ctx: API context for logging.

        Returns:
            Vector database interface implementation.

        Raises:
            ValueError: If vector DB provider is unknown.
        """
        if config.VECTOR_DB_PROVIDER == VectorDBProvider.VESPA:
            from airweave.search.spotlight.external.vector_database.vespa import (
                VespaVectorDB,
            )

            return await VespaVectorDB.create(ctx)

        raise ValueError(f"Unknown vector DB provider: {config.VECTOR_DB_PROVIDER}")

    async def close(self) -> None:
        """Clean up all resources."""
        await self.db.close()
        await self.llm.close()
        await self.dense_embedder.close()
        await self.sparse_embedder.close()
        await self.vector_db.close()
