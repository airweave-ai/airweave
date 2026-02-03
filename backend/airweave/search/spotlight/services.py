"""Services container for spotlight search.

This is the composition root - where external dependencies are wired together.
"""

from airweave.api.context import ApiContext
from airweave.search.spotlight.config import DatabaseImpl, LLMProvider, config
from airweave.search.spotlight.external.database import SpotlightDatabaseInterface
from airweave.search.spotlight.external.llm import SpotlightLLMInterface
from airweave.search.spotlight.external.llm.registry import get_model_spec
from airweave.search.spotlight.external.tokenizer import SpotlightTokenizerInterface
from airweave.search.spotlight.external.tokenizer.registry import (
    TokenizerType,
    is_encoding_supported,
)


class SpotlightServices:
    """Container for external dependencies.

    This is the composition root - where external dependencies are wired together.
    The planner uses these services:
    - services.db for metadata queries
    - services.tokenizer.count_tokens() for token counting
    - services.llm.model_spec for context limits
    - services.llm.structured_output() for LLM calls
    """

    def __init__(
        self,
        db: SpotlightDatabaseInterface,
        tokenizer: SpotlightTokenizerInterface,
        llm: SpotlightLLMInterface,
    ):
        """Initialize with external dependencies.

        Args:
            db: Database interface for metadata queries.
            tokenizer: Tokenizer interface for token counting.
            llm: LLM interface for structured output.
        """
        self.db = db
        self.tokenizer = tokenizer
        self.llm = llm

    @classmethod
    async def create(cls, ctx: ApiContext) -> "SpotlightServices":
        """Create services based on config.

        Args:
            ctx: API context for organization scoping and logging.

        Returns:
            SpotlightServices instance with all dependencies wired.
        """
        db = await cls._create_db(ctx)
        tokenizer = cls._create_tokenizer()
        llm = cls._create_llm(ctx, tokenizer)

        return cls(db=db, tokenizer=tokenizer, llm=llm)

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
        """Create tokenizer based on model spec.

        The model spec specifies which tokenizer type and encoding to use.
        Validates that the tokenizer type supports the encoding.

        Returns:
            Tokenizer interface implementation.

        Raises:
            ValueError: If tokenizer type is unknown or doesn't support the encoding.
        """
        model_spec = get_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)

        # Validate encoding is supported by the tokenizer type
        if not is_encoding_supported(model_spec.tokenizer_type, model_spec.tokenizer_encoding):
            raise ValueError(
                f"Tokenizer '{model_spec.tokenizer_type.value}' does not support "
                f"encoding '{model_spec.tokenizer_encoding.value}'"
            )

        if model_spec.tokenizer_type == TokenizerType.TIKTOKEN:
            from airweave.search.spotlight.external.tokenizer.tiktoken import (
                TiktokenTokenizer,
            )

            return TiktokenTokenizer(model_spec.tokenizer_encoding)

        raise ValueError(f"Unknown tokenizer type: {model_spec.tokenizer_type}")

    @staticmethod
    def _create_llm(
        ctx: ApiContext,
        tokenizer: SpotlightTokenizerInterface,
    ) -> SpotlightLLMInterface:
        """Create LLM based on config.

        Looks up the model spec from the registry.

        Args:
            ctx: API context for logging.
            tokenizer: Tokenizer for accurate token counting in rate limiting.

        Returns:
            LLM interface implementation.

        Raises:
            ValueError: If LLM provider is unknown.
        """
        model_spec = get_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)

        if config.LLM_PROVIDER == LLMProvider.CEREBRAS:
            from airweave.search.spotlight.external.llm.cerebras import CerebrasLLM

            return CerebrasLLM(
                model_spec=model_spec,
                tokenizer=tokenizer,
                logger=ctx.logger,
            )

        raise ValueError(f"Unknown LLM provider: {config.LLM_PROVIDER}")

    async def close(self) -> None:
        """Clean up all resources."""
        await self.db.close()
        await self.llm.close()
