"""Services container for spotlight search.

This is the composition root - where external dependencies are wired together.
"""

from airweave.api.context import ApiContext
from airweave.search.spotlight.config import DatabaseImpl, TokenizerImpl, config
from airweave.search.spotlight.external.database import SpotlightDatabaseInterface
from airweave.search.spotlight.external.llm import SpotlightLLMInterface
from airweave.search.spotlight.external.llm.registry import LLMProvider, get_model_spec
from airweave.search.spotlight.external.tokenizer import SpotlightTokenizerInterface


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
            ctx: API context for organization scoping (used by database).

        Returns:
            SpotlightServices instance with all dependencies wired.
        """
        db = await cls._create_db(ctx)
        tokenizer = cls._create_tokenizer()
        llm = cls._create_llm()

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
        """Create tokenizer based on config.

        Looks up the model spec to determine the required encoding.

        Returns:
            Tokenizer interface implementation.

        Raises:
            ValueError: If tokenizer implementation is unknown.
        """
        model_spec = get_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)

        if config.TOKENIZER_IMPL == TokenizerImpl.TIKTOKEN:
            from airweave.search.spotlight.external.tokenizer.tiktoken import (
                TiktokenTokenizer,
            )

            return TiktokenTokenizer(model_spec.tokenizer_encoding)

        raise ValueError(f"Unknown tokenizer implementation: {config.TOKENIZER_IMPL}")

    @staticmethod
    def _create_llm() -> SpotlightLLMInterface:
        """Create LLM based on config.

        Looks up the model spec from the registry.

        Returns:
            LLM interface implementation.

        Raises:
            ValueError: If LLM provider is unknown.
        """
        model_spec = get_model_spec(config.LLM_PROVIDER, config.LLM_MODEL)

        if config.LLM_PROVIDER == LLMProvider.CEREBRAS:
            from airweave.search.spotlight.external.llm.cerebras import CerebrasLLM

            return CerebrasLLM(model_spec)

        raise ValueError(f"Unknown LLM provider: {config.LLM_PROVIDER}")

    async def close(self) -> None:
        """Clean up all resources."""
        await self.db.close()
        await self.llm.close()
