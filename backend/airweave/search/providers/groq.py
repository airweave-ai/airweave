"""Groq provider implementation.

Supports text generation, structured output, and reranking via structured output.
Does not support embeddings.
"""

import json
from typing import Any, Dict, List, Optional

from groq import AsyncGroq
from pydantic import BaseModel
from tiktoken import Encoding

from airweave.api.context import ApiContext

from ._base import BaseProvider, ProviderError
from .schemas import ProviderModelSpec


class GroqProvider(BaseProvider):
    """Groq LLM provider."""

    MAX_COMPLETION_TOKENS = 10000
    MAX_STRUCTURED_OUTPUT_TOKENS = 2000
    RERANK_SAFETY_TOKENS = 1500

    def __init__(self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext) -> None:
        """Initialize Groq provider with model specs from defaults.yml."""
        super().__init__(api_key, model_spec, ctx)

        try:
            self.client = AsyncGroq(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Groq client: {e}") from e

        self.ctx.logger.debug(f"[GroqProvider] Initialized with model spec: {model_spec}")

        self.llm_tokenizer: Optional[Encoding] = None
        self.rerank_tokenizer: Optional[Encoding] = None

        if model_spec.llm_model:
            self.llm_tokenizer = self._load_tokenizer(model_spec.llm_model.tokenizer, "llm")

        if model_spec.rerank_model and model_spec.rerank_model.tokenizer:
            self.rerank_tokenizer = self._load_tokenizer(
                model_spec.rerank_model.tokenizer, "rerank"
            )

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion using Groq."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Groq provider")

        if not messages:
            raise ValueError("Cannot generate completion with empty messages")

        try:
            response = await self.client.chat.completions.create(
                model=self.model_spec.llm_model.name,
                messages=messages,
                max_completion_tokens=self.MAX_COMPLETION_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"Groq completion API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Groq returned empty completion content")

        return content

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using Groq JSON schema mode."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Groq provider")

        if not messages:
            raise ValueError("Cannot generate structured output with empty messages")

        if not schema:
            raise ValueError("Schema is required for structured output")

        try:
            response = await self.client.chat.completions.create(
                model=self.model_spec.llm_model.name,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__.lower(),
                        "schema": schema.model_json_schema(),
                    },
                },
                max_completion_tokens=self.MAX_STRUCTURED_OUTPUT_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"Groq structured output API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Groq returned empty structured output content")

        try:
            parsed = schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise ProviderError(f"Groq returned invalid JSON: {e}") from e
        except Exception as e:
            raise ProviderError(f"Failed to parse Groq structured output: {e}") from e

        return parsed

    async def embed(self, texts: List[str], dimensions: Optional[int] = None) -> List[List[float]]:
        """Not supported by Groq."""
        raise NotImplementedError("Groq does not support embeddings")

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Rerank documents using Groq structured output."""
        from airweave.search.prompts import RERANKING_SYSTEM_PROMPT

        if not self.model_spec.rerank_model:
            raise RuntimeError("Rerank model not configured for Groq provider")

        if not documents:
            raise ValueError("Cannot rerank empty document list")

        if top_n < 1:
            raise ValueError(f"top_n must be >= 1, got {top_n}")

        # Define schema for reranking
        class RankedResult(BaseModel):
            index: int
            relevance_score: float

        class RerankResult(BaseModel):
            rankings: List[RankedResult]

        # Budget documents to fit in context window
        chosen, user_prompt = self._budget_documents_for_reranking(query, documents)

        # Call LLM with structured output
        rerank_result = await self.structured_output(
            messages=[
                {"role": "system", "content": RERANKING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            schema=RerankResult,
        )

        if not rerank_result.rankings:
            raise ProviderError("Groq returned empty rankings")

        # Map rankings relative to chosen subset back to original indices
        mapped: List[Dict[str, Any]] = []
        for r in rerank_result.rankings:
            if r.index < 0 or r.index >= len(chosen):
                continue
            mapped.append({"index": chosen[r.index], "relevance_score": r.relevance_score})

        return mapped[:top_n]

    def _budget_documents_for_reranking(
        self, query: str, documents: List[str]
    ) -> tuple[List[int], str]:
        """Select maximum documents that fit in context window and build prompt."""
        from airweave.search.prompts import RERANKING_SYSTEM_PROMPT

        if not self.rerank_tokenizer:
            raise RuntimeError(
                "Rerank tokenizer not initialized. "
                "Ensure tokenizer is configured in defaults.yml for Groq rerank model."
            )

        if not self.model_spec.rerank_model or not self.model_spec.rerank_model.context_window:
            raise RuntimeError("Context window required for Groq reranking")

        context_window = self.model_spec.rerank_model.context_window

        system_prompt = RERANKING_SYSTEM_PROMPT
        header = f"Query: {query}\n\nSearch Results:\n"
        footer = "\n\nPlease rerank these results from most to least relevant to the query."

        # Calculate static token costs
        static_tokens = sum(
            [
                self.count_tokens(system_prompt, self.rerank_tokenizer),
                self.count_tokens(header, self.rerank_tokenizer),
                self.count_tokens(footer, self.rerank_tokenizer),
            ]
        )

        budget = (
            context_window
            - static_tokens
            - self.MAX_STRUCTURED_OUTPUT_TOKENS
            - self.RERANK_SAFETY_TOKENS
        )

        if budget <= 0:
            raise RuntimeError("Insufficient token budget for reranking prompts")

        # Fit as many documents as possible within budget
        chosen: List[int] = []
        running = 0
        for i, doc in enumerate(documents):
            piece = f"[{i}] {doc}"
            piece_tokens = self.count_tokens(piece, self.rerank_tokenizer)
            separator_tokens = 2 if i > 0 else 0  # "\n\n" between documents

            if running + piece_tokens + separator_tokens <= budget:
                chosen.append(i)
                running += piece_tokens + separator_tokens
            else:
                break

        # If no documents fit, we can't proceed
        if not chosen:
            first_doc_tokens = (
                self.count_tokens(f"[0] {documents[0]}", self.rerank_tokenizer)
                if documents
                else "N/A"
            )
            raise RuntimeError(
                f"No documents fit within token budget of {budget}. "
                f"Context window: {context_window}, static tokens: {static_tokens}, "
                f"first document tokens: {first_doc_tokens}. "
                "Documents may be too large or context window too small."
            )

        formatted_docs = "\n\n".join([f"[{i}] {documents[i]}" for i in chosen])
        user_prompt = f"{header}{formatted_docs}{footer}"

        return chosen, user_prompt
