"""Base provider for LLM operations."""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from airweave.api.context import ApiContext
from airweave.platform.tokenizers import BaseTokenizer, get_tokenizer

from .schemas import ProviderModelSpec


class ProviderError(RuntimeError):
    """Base exception for provider issues with retryability metadata."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class BaseProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext) -> None:
        """Initialize provider with API key and model specifications."""
        self.api_key = api_key
        self.model_spec = model_spec
        self.ctx = ctx

    @staticmethod
    def is_retryable_error(error: Exception) -> bool:
        """Check if error should trigger provider fallback.

        In a multi-provider system, most errors are "retryable" because each provider
        has different capabilities, credentials, and availability. We try the next
        provider unless the error indicates a fundamental problem with the request itself.

        Provider-specific errors (SHOULD fallback):
        - 401, 403: Auth errors (each provider has its own API key)
        - 404: Not found (model might exist on another provider)
        - 429: Rate limiting (try provider with capacity)
        - 500, 502, 503, 504: Server errors (provider infrastructure issues)
        - 400, 422: Validation errors (might be provider-specific schema requirements)

        Request-level errors (SHOULD NOT fallback):
        - Programming errors (ValueError, TypeError, AttributeError, etc.)
        - These indicate bugs in our code, not provider issues

        Args:
            error: Exception to check

        Returns:
            True if error should trigger fallback to next provider
        """
        if isinstance(error, ProviderError):
            return error.retryable

        error_str = str(error).lower()

        # Check for HTTP status codes and error patterns in error message
        retryable_patterns = [
            r"400",  # Bad request
            r"401",  # Unauthorized
            r"403",  # Forbidden
            r"404",  # Not found
            r"422",  # Unprocessable entity
            r"429",  # Too many requests
            r"500",  # Internal server error
            r"502",  # Bad gateway
            r"503",  # Service unavailable
            r"504",  # Gateway timeout
            r"too[_\s]many[_\s]requests",
            r"rate[_\s]limit",
            r"queue[_\s]exceeded",
            r"server[_\s]error",
        ]

        for pattern in retryable_patterns:
            if re.search(pattern, error_str):
                return True

        return False

    def _load_tokenizer(self, tokenizer_name: str, model_type: str) -> Optional[BaseTokenizer]:
        """Load a tokenizer by name with consistent error handling.

        Uses the unified tokenizer factory to support tiktoken, Mistral, and
        other tokenizer backends based on the name from defaults.yml.
        """
        try:
            return get_tokenizer(tokenizer_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load {model_type} tokenizer '{tokenizer_name}': {e}"
            ) from e

    def count_tokens(self, text: str, tokenizer: Optional[BaseTokenizer]) -> int:
        """Count tokens in text using a specific tokenizer."""
        if tokenizer is None:
            raise RuntimeError("Tokenizer not initialized for token counting")
        if text is None:
            return 0
        return tokenizer.count_tokens(text)

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion."""
        pass

    @abstractmethod
    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output conforming to Pydantic schema."""
        pass

    @abstractmethod
    async def embed(self, texts: List[str], dimensions: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings for text.

        Args:
            texts: List of texts to embed
            dimensions: Optional target dimensions for Matryoshka truncation.
                       If None, uses the model's native dimensions.
                       Supported by models like text-embedding-3-large (3072 native).
        """
        pass

    @abstractmethod
    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Rerank documents by relevance to query."""
        pass
