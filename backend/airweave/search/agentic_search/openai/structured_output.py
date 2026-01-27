"""OpenAI Structured Output Client for agentic search.

A lightweight client for reasoning models (gpt-5.2, gpt-5, etc.) with:
- Structured output via Responses API
- Token counting and context window management
- Smart truncation when context is exceeded

This is separate from the search module's OpenAIProvider because:
- It's specialized for reasoning models with the `reasoning` parameter
- It handles multi-turn context management (truncating old iterations)
- It doesn't need embeddings, reranking, or other search operations
"""

from typing import Literal, TypeVar

import tiktoken
from pydantic import BaseModel

from airweave.api.context import ApiContext
from airweave.core.config import settings
from openai import AsyncOpenAI

T = TypeVar("T", bound=BaseModel)

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


class StructuredOutputClient:
    """Client for OpenAI reasoning models with structured output.

    Features:
    - Structured output via Pydantic schemas
    - Token counting and context window management
    - Configurable reasoning effort (none, low, medium, high, xhigh)

    Usage:
        client = StructuredOutputClient(model="gpt-5.2", reasoning_effort="medium")
        plan = await client.structured_output(prompt, SearchPlan)
    """

    # Model configurations
    MODELS = {
        "gpt-5.2": {
            "context_window": 400_000,
            "max_output_tokens": 128_000,
            "tokenizer": "o200k_base",
        },
        "gpt-5": {
            "context_window": 200_000,
            "max_output_tokens": 100_000,
            "tokenizer": "o200k_base",
        },
        "gpt-5-mini": {
            "context_window": 200_000,
            "max_output_tokens": 100_000,
            "tokenizer": "o200k_base",
        },
    }

    # Reserve tokens for output and reasoning
    # Reasoning models can use many tokens for thinking
    OUTPUT_RESERVE = 50_000

    def __init__(
        self,
        model: str = "gpt-5.2",
        reasoning_effort: ReasoningEffort = "medium",
        ctx: ApiContext | None = None,
    ) -> None:
        """Initialize the reasoning client.

        Args:
            model: Model to use (gpt-5.2, gpt-5, o4-mini, etc.)
            reasoning_effort: How much reasoning to use (none, low, medium, high, xhigh)
            ctx: API context for logging (optional)
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = AsyncOpenAI(api_key=api_key, timeout=300.0, max_retries=2)
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.ctx = ctx

        # Get model config
        if model not in self.MODELS:
            # Default to gpt-5.2 config for unknown models
            self._config = self.MODELS["gpt-5.2"]
            self._log(f"Unknown model {model}, using gpt-5.2 config")
        else:
            self._config = self.MODELS[model]

        # Initialize tokenizer
        try:
            self._tokenizer = tiktoken.get_encoding(self._config["tokenizer"])
        except Exception as e:
            raise RuntimeError(f"Failed to load tokenizer: {e}") from e

        self._log(
            f"Initialized: model={model}, "
            f"context_window={self._config['context_window']:,}, "
            f"reasoning_effort={reasoning_effort}"
        )

    def _log(self, message: str, level: str = "debug") -> None:
        """Log a message if context is available."""
        if self.ctx:
            logger = getattr(self.ctx.logger, level)
            logger(f"[StructuredOutputClient] {message}")

    @property
    def context_window(self) -> int:
        """Total context window size in tokens."""
        return self._config["context_window"]

    @property
    def max_input_tokens(self) -> int:
        """Maximum tokens available for input (context_window - output_reserve)."""
        return self.context_window - self.OUTPUT_RESERVE

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self._tokenizer.encode(text, allowed_special="all"))

    def check_fits_context(self, prompt: str) -> tuple[bool, int]:
        """Check if a prompt fits in the context window.

        Args:
            prompt: The full prompt text

        Returns:
            Tuple of (fits, token_count)
        """
        token_count = self.count_tokens(prompt)
        fits = token_count <= self.max_input_tokens
        return fits, token_count

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
    ) -> T:
        """Generate structured output using a reasoning model.

        Args:
            prompt: The prompt text
            schema: Pydantic model class for the response

        Returns:
            Parsed response matching the schema

        Raises:
            ValueError: If prompt exceeds context window
            RuntimeError: If API call fails
        """
        # Check token count
        fits, token_count = self.check_fits_context(prompt)
        if not fits:
            raise ValueError(
                f"Prompt exceeds context window: {token_count:,} tokens > "
                f"{self.max_input_tokens:,} max input tokens "
                f"(context_window={self.context_window:,}, reserve={self.OUTPUT_RESERVE:,})"
            )

        self._log(
            f"Calling {self.model} with {token_count:,} tokens, "
            f"reasoning_effort={self.reasoning_effort}"
        )

        try:
            response = await self.client.responses.parse(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                text_format=schema,
                reasoning={"effort": self.reasoning_effort},
            )

            # Check for incomplete response
            if response.status == "incomplete":
                reason = (
                    response.incomplete_details.reason if response.incomplete_details else "unknown"
                )
                raise RuntimeError(f"Model returned incomplete response: {reason}")

            # Check for refusal
            if response.output and response.output[0].content:
                first_content = response.output[0].content[0]
                if hasattr(first_content, "refusal") and first_content.refusal:
                    raise RuntimeError(f"Model refused request: {first_content.refusal}")

            parsed = response.output_parsed
            if not parsed:
                raise RuntimeError("Model returned empty structured output")

            # Log token usage
            if response.usage:
                reasoning_tokens = (
                    response.usage.output_tokens_details.reasoning_tokens
                    if response.usage.output_tokens_details
                    else 0
                )
                self._log(
                    f"Token usage: input={response.usage.input_tokens:,}, "
                    f"output={response.usage.output_tokens:,}, "
                    f"reasoning={reasoning_tokens:,}"
                )

            return parsed

        except ValueError:
            # Re-raise context window errors
            raise
        except Exception as e:
            self._log(f"API call failed: {e}", level="error")
            raise RuntimeError(f"Structured output API call failed: {e}") from e
