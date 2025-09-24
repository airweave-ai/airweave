"""Lightweight OpenAI client (Async + Structured Outputs)."""

from __future__ import annotations

import os
import re
from typing import Optional, Type, Union
from enum import Enum

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from monke.utils.logging import get_logger


class ModelName(str, Enum):
    GPT_41_MINI = "gpt-4.1-mini"
    GPT_41 = "gpt-4.1"
    GPT_4O = "gpt-4o"
    GPT_5 = "gpt-5"
    O3_MINI = "o3-mini"
    O1 = "o1"


class LLMClient:
    """
    Async wrapper around OpenAI's Responses API.

    - Uses AsyncOpenAI (official async SDK client)
    - Structured Outputs via `responses.parse`: pass a Pydantic model and get a parsed instance back
    - Falls back to JSON Schema response_format (strict) if `parse()` isn't available
    """

    def __init__(self, model_override: Optional[Union["ModelName", str]] = None):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required in environment")

        self.client = AsyncOpenAI()

        self.model = self._resolve_model(model_override)
        self.logger = get_logger("llm_client")

    def _resolve_model(self, model_override: Optional[Union["ModelName", str]]) -> str:
        """Normalize provided model or fall back to environment default (no hard validation)."""
        override_str = (
            model_override.value if isinstance(model_override, ModelName) else model_override
        )
        candidate = override_str or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        return candidate

    def _sampling_kwargs(self, temperature: float) -> dict:
        """Build sampling kwargs, omitting temperature for models that don't accept it."""
        models_without_temp_prefixes = (ModelName.GPT_5.value,)
        if any(self.model.startswith(prefix) for prefix in models_without_temp_prefixes):
            return {}
        return {"temperature": temperature}

    async def generate_text(self, instruction: str) -> str:
        """Simple text generation using the Responses API."""
        resp = await self.client.responses.create(
            model=self.model,
            instructions="You generate fresh, varied test data.",
            input=instruction,
            **self._sampling_kwargs(0.8),
        )
        return getattr(resp, "output_text", "") or ""

    async def generate_structured(self, schema: Type[BaseModel], instruction: str) -> BaseModel:
        """
        Generate an object that matches the given Pydantic schema using Structured Outputs.

        Primary path: `responses.parse(...)` with `text_format=schema` (Pydantic class).
        Fallback:     `responses.create(...)` with response_format=json_schema + strict, then Pydantic-validate.
        """

        # --- Preferred: native structured parsing ---
        try:
            resp = await self.client.responses.parse(
                model=self.model,
                input=instruction,  # you can also pass a list of role/content items if you prefer
                instructions="Return only a single object that conforms to the provided schema.",
                text_format=schema,  # <- Pydantic class; SDK converts to JSON Schema and parses output
                **self._sampling_kwargs(0.7),
            )
            parsed = getattr(resp, "output_parsed", None)
            if parsed is not None:
                return parsed  # already a Pydantic instance
            # If for some reason parsed is None, fall through to the defensive fallback below.
            self.logger.warning(
                "Structured parse returned no parsed object; attempting JSON Schema fallback."
            )
        except Exception as e:
            # Common causes: older SDK version, transient parsing issues, or unsupported model.
            self.logger.exception("Structured parse failed; attempting JSON Schema fallback: %s", e)

        # --- Defensive fallback: strict JSON Schema response_format ---
        # Convert the Pydantic model to a JSON Schema and enforce strict adherence server-side.
        rf = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        }

        resp2 = await self.client.responses.create(
            model=self.model,
            input=instruction,
            instructions="Return ONLY a single JSON object that matches the schema. No prose.",
            response_format=rf,
            **self._sampling_kwargs(0.7),
        )

        raw = getattr(resp2, "output_text", "") or ""
        # Validate the raw JSON text with Pydantic. If the model wrapped it, extract the first JSON object.
        try:
            return schema.model_validate_json(raw)
        except ValidationError:
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                # Nothing JSON-like to validate
                raise
            return schema.model_validate_json(m.group(0))
