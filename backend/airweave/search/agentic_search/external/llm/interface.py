"""LLM interface for agentic search."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from airweave.search.agentic_search.external.llm.registry import LLMModelSpec

T = TypeVar("T", bound=BaseModel)


class AgenticSearchLLMInterface(Protocol):
    """LLM interface for agentic search."""

    @property
    def model_spec(self) -> LLMModelSpec:
        """Get the model specification."""
        ...

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Generate structured output matching the schema.

        Args:
            prompt: The user prompt (dynamic context: collection metadata, results, history).
            schema: Pydantic model class for the response.
            system_prompt: System prompt (static instructions: task description, rules).
                Sent as a system message so the model treats these as higher-priority
                instructions separate from the user context.
        """
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP client)."""
        ...
