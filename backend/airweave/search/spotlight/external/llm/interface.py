"""LLM interface for spotlight search."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from airweave.search.spotlight.external.llm.registry import LLMModelSpec

T = TypeVar("T", bound=BaseModel)


class SpotlightLLMInterface(Protocol):
    """LLM interface for spotlight search."""

    @property
    def model_spec(self) -> LLMModelSpec:
        """Get the model specification."""
        ...

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
    ) -> T:
        """Generate structured output matching the schema."""
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP client)."""
        ...
