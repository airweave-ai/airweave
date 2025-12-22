"""Cerebras provider implementation.

Supports text generation and structured output.
Does not support embeddings or reranking.
"""

import json
from typing import Any, Dict, List, Optional

from cerebras.cloud.sdk import AsyncCerebras
from pydantic import BaseModel
from tiktoken import Encoding

from airweave.api.context import ApiContext

from ._base import BaseProvider, ProviderError
from .schemas import ProviderModelSpec


class CerebrasProvider(BaseProvider):
    """Cerebras LLM provider."""

    MAX_COMPLETION_TOKENS = 10000
    MAX_STRUCTURED_OUTPUT_TOKENS = 2000

    def __init__(self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext) -> None:
        """Initialize Cerebras provider with model specs from defaults.yml."""
        super().__init__(api_key, model_spec, ctx)

        try:
            # Set 30s timeout to prevent indefinite hangs
            print(f"[CEREBRAS DEBUG INIT] Initializing AsyncCerebras client with 30s timeout")
            self.client = AsyncCerebras(api_key=api_key, timeout=30.0)
            print(f"[CEREBRAS DEBUG INIT] ✓ Client initialized successfully")
        except Exception as e:
            print(f"[CEREBRAS DEBUG INIT] ✗ Failed to initialize client: {e}")
            raise RuntimeError(f"Failed to initialize Cerebras client: {e}") from e

        print(f"[CEREBRAS DEBUG INIT] Model: {model_spec.llm_model.name if model_spec.llm_model else 'None'}")
        print(f"[CEREBRAS DEBUG INIT] Context window: {model_spec.llm_model.context_window if model_spec.llm_model else 'None'}")
        self.ctx.logger.debug(f"[CerebrasProvider] Initialized with model spec: {model_spec}")

        self.llm_tokenizer: Optional[Encoding] = None

        if model_spec.llm_model:
            self.llm_tokenizer = self._load_tokenizer(model_spec.llm_model.tokenizer, "llm")

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion using Cerebras."""
        import time
        
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Cerebras provider")

        if not messages:
            raise ValueError("Cannot generate completion with empty messages")

        # Log request details
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        print(f"[CEREBRAS DEBUG] Starting API call")
        print(f"[CEREBRAS DEBUG] Model: {self.model_spec.llm_model.name}")
        print(f"[CEREBRAS DEBUG] Messages: {len(messages)}")
        print(f"[CEREBRAS DEBUG] Total chars: {total_chars}")
        print(f"[CEREBRAS DEBUG] Est. input tokens: {estimated_tokens}")
        print(f"[CEREBRAS DEBUG] Max completion tokens: {self.MAX_COMPLETION_TOKENS}")
        print(f"[CEREBRAS DEBUG] Timeout: 30s")

        start_time = time.time()
        try:
            print(f"[CEREBRAS DEBUG] Sending request to Cerebras API at {time.time():.2f}...")
            response = await self.client.chat.completions.create(
                model=self.model_spec.llm_model.name,
                messages=messages,
                max_completion_tokens=self.MAX_COMPLETION_TOKENS,
            )
            elapsed = time.time() - start_time
            print(f"[CEREBRAS DEBUG] ✓ Response received in {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[CEREBRAS DEBUG] ✗ API call failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
            raise RuntimeError(f"Cerebras completion API call failed: {e}") from e

        # Extract content from response
        content = response.choices[0].message.content
        if not content:
            print(f"[CEREBRAS DEBUG] ✗ Empty content in response")
            raise ProviderError("Cerebras returned empty completion content")

        print(f"[CEREBRAS DEBUG] ✓ Got {len(content)} chars response")
        return content

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using Cerebras JSON schema mode."""
        import time
        
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Cerebras provider")

        if not messages:
            raise ValueError("Cannot generate structured output with empty messages")

        if not schema:
            raise ValueError("Schema is required for structured output")

        # Build JSON schema (now provider-agnostic models are compatible)
        try:
            schema_json = schema.model_json_schema()
        except Exception as e:
            raise RuntimeError(f"Failed to build JSON schema from Pydantic model: {e}") from e

        # Pydantic emits minItems/maxItems for tuple schemas; Cerebras rejects those.
        # Normalize arrays: drop min/max and, when prefixItems present, set items: false.
        schema_json = self._normalize_arrays_for_cerebras(schema_json)

        # Log request details
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        print(f"[CEREBRAS DEBUG STRUCTURED] Starting API call")
        print(f"[CEREBRAS DEBUG STRUCTURED] Model: {self.model_spec.llm_model.name}")
        print(f"[CEREBRAS DEBUG STRUCTURED] Schema: {schema.__name__}")
        print(f"[CEREBRAS DEBUG STRUCTURED] Total chars: {total_chars}")
        print(f"[CEREBRAS DEBUG STRUCTURED] Timeout: 30s")

        start_time = time.time()
        try:
            # Strict schema mode (preferred)
            print(f"[CEREBRAS DEBUG STRUCTURED] Sending request at {time.time():.2f}...")
            response = await self.client.chat.completions.create(
                model=self.model_spec.llm_model.name,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__.lower(),
                        "strict": True,
                        "schema": schema_json,
                    },
                },
                max_completion_tokens=self.MAX_STRUCTURED_OUTPUT_TOKENS,
            )
            elapsed = time.time() - start_time
            print(f"[CEREBRAS DEBUG STRUCTURED] ✓ Response received in {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[CEREBRAS DEBUG STRUCTURED] ✗ API call failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
            raise RuntimeError(f"Cerebras structured output API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Cerebras returned empty structured output content")

        try:
            parsed = schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise ProviderError(f"Cerebras returned invalid JSON: {e}") from e
        except Exception as e:
            raise ProviderError(f"Failed to parse Cerebras structured output: {e}") from e

        return parsed

    def _normalize_arrays_for_cerebras(self, schema_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Remove minItems/maxItems and enforce items:false when prefixItems exist.

        Cerebras accepts fixed-length arrays via prefixItems + items:false, but rejects
        minItems/maxItems. Pydantic emits both for Tuple[...] schemas. This normalizer
        removes min/max everywhere and sets items:false when prefixItems is present.
        """
        import copy

        normalized = copy.deepcopy(schema_dict)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "array":
                    node.pop("minItems", None)
                    node.pop("maxItems", None)
                    if "prefixItems" in node and node.get("items") is not False:
                        node["items"] = False
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(normalized)
        return normalized

    # Removed sanitizer; models are now provider-agnostic

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Not supported by Cerebras."""
        raise NotImplementedError("Cerebras does not support embeddings")

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Not supported by Cerebras."""
        raise NotImplementedError("Cerebras does not support reranking")
