"""In-memory fake for LLMProtocol."""

from typing import TypeVar

from pydantic import BaseModel

from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMToolResponse

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """In-memory fake for LLMProtocol.

    Seed responses before use. Calls are recorded for verification.
    """

    def __init__(self, model_spec: LLMModelSpec) -> None:
        self._model_spec = model_spec
        self._structured_output_results: list = []
        self._tool_responses: list[LLMToolResponse] = []
        self._calls: list[tuple] = []

    def seed_structured_output(self, result: BaseModel) -> None:
        """Seed a result to be returned by next structured_output call."""
        self._structured_output_results.append(result)

    def seed_tool_response(self, response: LLMToolResponse) -> None:
        """Seed a response to be returned by next create_with_tools call."""
        self._tool_responses.append(response)

    @property
    def model_spec(self) -> LLMModelSpec:
        """Get the model specification."""
        return self._model_spec

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Return next seeded structured output result."""
        self._calls.append(("structured_output", prompt, schema, system_prompt))
        if not self._structured_output_results:
            raise RuntimeError("FakeLLM: no seeded structured_output results")
        return self._structured_output_results.pop(0)  # type: ignore[no-any-return]

    async def create_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse:
        """Return next seeded tool response."""
        self._calls.append(("create_with_tools", messages, tools, system_prompt))
        if not self._tool_responses:
            raise RuntimeError("FakeLLM: no seeded tool responses")
        return self._tool_responses.pop(0)

    async def close(self) -> None:
        """No-op cleanup."""
        self._calls.append(("close",))
