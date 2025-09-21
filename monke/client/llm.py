"""Multi-provider LLM client (Async + Structured Outputs)."""

from __future__ import annotations

import os
import re
from typing import Optional, Type, Any

from pydantic import BaseModel, ValidationError

from monke.utils.logging import get_logger


class ProviderType:
    """LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"


class LLMClient:
    """
    Multi-provider async LLM client.

    - Supports OpenAI, Anthropic, and Mistral APIs
    - Structured Outputs via provider-specific implementations
    - Provider detection based on available environment variables
    - Priority: OpenAI > Anthropic > Mistral
    """

    def __init__(self, model_override: Optional[str] = None):
        self.logger = get_logger("llm_client")

        self.provider = self._detect_provider()
        self.client = self._initialize_client()

        self.model = self._get_model(model_override)

    def _detect_provider(self) -> str:
        """Detect which provider to use based on available API keys."""
        if os.getenv("OPENAI_API_KEY"):
            return ProviderType.OPENAI
        elif os.getenv("ANTHROPIC_API_KEY"):
            return ProviderType.ANTHROPIC
        elif os.getenv("MISTRAL_API_KEY"):
            return ProviderType.MISTRAL
        else:
            raise RuntimeError(
                "No API key found. Please set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, or MISTRAL_API_KEY"
            )

    def _initialize_client(self) -> Any:
        """Initialize the client based on detected provider."""
        if self.provider == ProviderType.OPENAI:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise RuntimeError(
                    "OpenAI package not installed. Run: pip install openai>=1.40.0"
                )
            base_url = os.getenv("OPENAI_BASE_URL")
            return AsyncOpenAI(base_url=base_url) if base_url else AsyncOpenAI()

        elif self.provider == ProviderType.ANTHROPIC:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise RuntimeError(
                    "Anthropic package not installed. Run: pip install anthropic"
                )
            return AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        elif self.provider == ProviderType.MISTRAL:
            try:
                from mistralai.async_client import MistralAsyncClient
            except ImportError:
                raise RuntimeError(
                    "Mistral package not installed. Run: pip install mistralai"
                )
            return MistralAsyncClient(api_key=os.getenv("MISTRAL_API_KEY"))

        else:
            raise RuntimeError(f"Unsupported provider: {self.provider}")

    def _get_model(self, model_override: Optional[str]) -> str:
        """Get the model name with provider-specific defaults."""
        if model_override:
            return model_override

        env_model = (
            os.getenv("OPENAI_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
            or os.getenv("MISTRAL_MODEL")
        )
        if env_model:
            return env_model

        # Provider-specific defaults
        if self.provider == ProviderType.OPENAI:
            return "gpt-4.1"
        elif self.provider == ProviderType.ANTHROPIC:
            return "claude-3-5-sonnet-20241022"
        elif self.provider == ProviderType.MISTRAL:
            return "mistral-large-latest"
        else:
            return "gpt-4.1"  # fallback

    async def generate_structured(
        self, schema: Type[BaseModel], instruction: str
    ) -> BaseModel:
        """Generate structured output that matches the given Pydantic schema."""
        if self.provider == ProviderType.OPENAI:
            return await self._generate_structured_openai(schema, instruction)
        elif self.provider == ProviderType.ANTHROPIC:
            return await self._generate_structured_anthropic(schema, instruction)
        elif self.provider == ProviderType.MISTRAL:
            return await self._generate_structured_mistral(schema, instruction)
        else:
            raise RuntimeError(
                f"Structured generation not implemented for provider: {self.provider}"
            )

    async def _generate_structured_openai(
        self, schema: Type[BaseModel], instruction: str
    ) -> BaseModel:
        """
        OpenAI structured generation using Structured Outputs.

        Primary path: `responses.parse(...)` with `text_format=schema` (Pydantic class).
        Fallback:     `responses.create(...)` with response_format=json_schema + strict, then Pydantic-validate.
        """
        # --- Preferred: native structured parsing ---
        try:
            resp = await self.client.responses.parse(
                model=self.model,
                input=instruction,
                instructions="Return only a single object that conforms to the provided schema.",
                text_format=schema,
                temperature=0.7,
            )
            parsed = getattr(resp, "output_parsed", None)
            if parsed is not None:
                return parsed
            self.logger.warning(
                "Structured parse returned no parsed object; attempting JSON Schema fallback."
            )
        except Exception as e:
            self.logger.exception(
                "Structured parse failed; attempting JSON Schema fallback: %s", e
            )

        # --- Defensive fallback: strict JSON Schema response_format ---
        return await self._fallback_json_parsing(schema, instruction, "openai")

    async def _generate_structured_anthropic(
        self, schema: Type[BaseModel], instruction: str
    ) -> BaseModel:
        """Anthropic structured generation using tool calling."""
        tool_definition = {
            "name": f"create_{schema.__name__.lower()}",
            "description": f"Create a {schema.__name__} object",
            "input_schema": schema.model_json_schema(),
        }

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=0.7,
            system="You are a helpful assistant that creates structured data objects.",
            messages=[{"role": "user", "content": instruction}],
            tools=[tool_definition],
            tool_choice={"type": "tool", "name": tool_definition["name"]},
        )

        for content in message.content:
            if content.type == "tool_use":
                return schema.model_validate(content.input)

        # Fallback to JSON parsing if no tool use
        return await self._fallback_json_parsing(schema, instruction, "anthropic")

    async def _generate_structured_mistral(
        self, schema: Type[BaseModel], instruction: str
    ) -> BaseModel:
        """Mistral structured generation using function calling."""
        function_definition = {
            "name": f"create_{schema.__name__.lower()}",
            "description": f"Create a {schema.__name__} object",
            "parameters": schema.model_json_schema(),
        }

        response = await self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates structured data objects.",
                },
                {"role": "user", "content": instruction},
            ],
            tools=[{"type": "function", "function": function_definition}],
            tool_choice="any",
            temperature=0.7,
            max_tokens=4000,
        )

        message = response.choices[0].message
        if message.tool_calls:
            import json

            function_args = json.loads(message.tool_calls[0].function.arguments)
            return schema.model_validate(function_args)

        # Fallback to JSON parsing if no tool calls
        return await self._fallback_json_parsing(schema, instruction, "mistral")

    async def _fallback_json_parsing(
        self, schema: Type[BaseModel], instruction: str, provider: str
    ) -> BaseModel:
        """Unified JSON parsing fallback for providers without native structured output."""
        json_instruction = f"{instruction}\n\nReturn only valid JSON matching this schema:\n{schema.model_json_schema()}"

        if provider == "openai":
            rf = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": True,
                },
            }
            resp = await self.client.responses.create(
                model=self.model,
                input=json_instruction,
                response_format=rf,
                temperature=0.7,
            )
            raw = getattr(resp, "output_text", "") or ""

        elif provider == "anthropic":
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.7,
                system="Return only valid JSON. No explanations.",
                messages=[{"role": "user", "content": json_instruction}],
            )
            raw = message.content[0].text if message.content else ""

        elif provider == "mistral":
            response = await self.client.chat(
                model=self.model,
                temperature=0.7,
                max_tokens=4000,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON. No explanations.",
                    },
                    {"role": "user", "content": json_instruction},
                ],
            )
            raw = response.choices[0].message.content if response.choices else ""

        else:
            raise RuntimeError(f"Unknown provider for fallback: {provider}")

        return self._parse_json_response(schema, raw)

    def _parse_json_response(self, schema: Type[BaseModel], raw: str) -> BaseModel:
        """Parse JSON response text into Pydantic model."""
        try:
            return schema.model_validate_json(raw)
        except ValidationError:
            # Try to extract JSON from response
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                raise ValueError(f"No valid JSON found in response: {raw}")
            return schema.model_validate_json(m.group(0))
