"""Mistral provider implementation.

Supports embeddings via Mistral's embedding API.
Supports text generation, structured output, and reranking via LLM.
"""

import hashlib
import json
import random
from typing import Any, Dict, List, Optional

try:
    from mistralai import Mistral
except ImportError:
    Mistral = None  # type: ignore[assignment]

from pydantic import BaseModel

from airweave.api.context import ApiContext
from airweave.platform.tokenizers import BaseTokenizer

from ._base import BaseProvider, ProviderError
from .schemas import ProviderModelSpec


class MistralProvider(BaseProvider):
    """Mistral embeddings and LLM provider."""

    MAX_EMBEDDING_BATCH_SIZE = 128
    MAX_TOKENS_PER_REQUEST = 8000
    MAX_COMPLETION_TOKENS = 10000
    MAX_STRUCTURED_OUTPUT_TOKENS = 2000
    RERANK_SAFETY_TOKENS = 1500

    def __init__(self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext) -> None:
        """Initialize Mistral provider with model specs from defaults.yml."""
        super().__init__(api_key, model_spec, ctx)

        self._mock_embeddings = bool(
            model_spec.embedding_model
            and model_spec.embedding_model.name
            and "mock" in model_spec.embedding_model.name.lower()
        )

        if not self._mock_embeddings and Mistral is None:
            raise ImportError(
                "mistralai package not installed. Install with: pip install mistralai"
            )

        self.client = None
        if not self._mock_embeddings:
            try:
                self.client = Mistral(api_key=api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Mistral client: {e}") from e

        # Initialize tokenizers (using unified tokenizer factory)
        self.llm_tokenizer: Optional[BaseTokenizer] = None
        self.rerank_tokenizer: Optional[BaseTokenizer] = None
        self.embedding_tokenizer: Optional[BaseTokenizer] = None

        if model_spec.llm_model:
            self.llm_tokenizer = self._load_tokenizer(model_spec.llm_model.tokenizer, "llm")

        if model_spec.rerank_model and model_spec.rerank_model.tokenizer:
            self.rerank_tokenizer = self._load_tokenizer(
                model_spec.rerank_model.tokenizer, "rerank"
            )

        if model_spec.embedding_model and model_spec.embedding_model.tokenizer:
            self.embedding_tokenizer = self._load_tokenizer(
                model_spec.embedding_model.tokenizer, "embedding"
            )

        if model_spec.embedding_model:
            self.ctx.logger.info(
                f"[MistralProvider] Using embedding model: {model_spec.embedding_model.name} "
                f"({model_spec.embedding_model.dimensions}-dim)"
            )
        if model_spec.llm_model:
            self.ctx.logger.info(f"[MistralProvider] Using LLM model: {model_spec.llm_model.name}")

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion using Mistral's native async API."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Mistral provider")

        if not messages:
            raise ValueError("Cannot generate completion with empty messages")

        if self.client is None:
            raise ProviderError("Mistral client is not initialized", retryable=False)

        try:
            # Use native async method (complete_async)
            response = await self.client.chat.complete_async(
                model=self.model_spec.llm_model.name,
                messages=messages,
                max_tokens=self.MAX_COMPLETION_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"Mistral completion API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Mistral returned empty completion content")

        return content

    def _build_schema_hint(self, schema: type[BaseModel]) -> str:
        """Build schema hint for JSON mode."""
        schema_json = schema.model_json_schema()
        return (
            f"\n\nYou MUST respond with valid JSON matching this exact schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n"
            f"Return ONLY the JSON object, no markdown or explanation."
        )

    def _augment_messages_with_schema(
        self, messages: List[Dict[str, str]], schema_hint: str
    ) -> List[Dict[str, str]]:
        """Inject schema hint into messages."""
        augmented = []
        for i, msg in enumerate(messages):
            if i == 0 and msg.get("role") == "system":
                augmented.append({"role": "system", "content": msg["content"] + schema_hint})
            else:
                augmented.append(msg)

        if not augmented or augmented[0].get("role") != "system":
            augmented.insert(
                0,
                {
                    "role": "system",
                    "content": f"You are a helpful assistant that outputs JSON.{schema_hint}",
                },
            )
        return augmented

    def _validate_structured_output_inputs(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> None:
        """Validate inputs for structured output."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for Mistral provider")
        if not messages:
            raise ValueError("Cannot generate structured output with empty messages")
        if not schema:
            raise ValueError("Schema is required for structured output")
        if self.client is None:
            raise ProviderError("Mistral client is not initialized", retryable=False)

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using Mistral's JSON mode with schema hints.

        Note: Mistral's chat.parse_async() doesn't handle all Pydantic schemas
        (fails on minItems/maxItems constraints). We use JSON mode instead and
        inject the schema into the prompt for guidance.

        See: https://docs.mistral.ai/capabilities/structured_output/json_mode
        """
        self._validate_structured_output_inputs(messages, schema)

        schema_hint = self._build_schema_hint(schema)
        augmented_messages = self._augment_messages_with_schema(messages, schema_hint)

        try:
            response = await self.client.chat.complete_async(
                model=self.model_spec.llm_model.name,
                messages=augmented_messages,
                response_format={"type": "json_object"},
                max_tokens=self.MAX_STRUCTURED_OUTPUT_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"Mistral structured output API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("Mistral returned empty structured output content")

        try:
            return schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise ProviderError(f"Mistral returned invalid JSON: {e}") from e
        except Exception as e:
            raise ProviderError(f"Failed to parse Mistral structured output: {e}") from e

    def _validate_embed_inputs(self, texts: List[str], dimensions: Optional[int]) -> int:
        """Validate embed inputs and return expected dimensions."""
        if not self.model_spec.embedding_model:
            raise RuntimeError("Embedding model not configured for Mistral provider")
        if not texts:
            raise ValueError("Cannot embed empty text list")
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} is empty")

        model_dimensions = self.model_spec.embedding_model.dimensions
        requested_dimensions = dimensions or model_dimensions

        if requested_dimensions != model_dimensions:
            raise ProviderError(
                f"Mistral embedding model '{self.model_spec.embedding_model.name}' "
                f"outputs fixed {model_dimensions} dimensions. "
                f"Requested {requested_dimensions} dimensions is not supported. "
                f"Update EMBEDDING_DIMENSIONS in .env to {model_dimensions}.",
                retryable=False,
            )
        return model_dimensions

    async def _embed_single_batch(self, batch: List[str], expected_dims: int) -> List[List[float]]:
        """Embed a single batch via API."""
        if self.client is None:
            raise ProviderError("Mistral client is not initialized", retryable=False)

        try:
            response = await self.client.embeddings.create_async(
                model=self.model_spec.embedding_model.name,
                inputs=batch,
            )
        except TypeError as exc:
            if "unexpected keyword argument 'inputs'" in str(exc):
                response = await self.client.embeddings.create_async(
                    model=self.model_spec.embedding_model.name,
                    input=batch,
                )
            else:
                raise

        if not response.data:
            raise ProviderError("Mistral returned no embeddings")

        batch_embeddings = [item.embedding for item in response.data]
        if len(batch_embeddings) != len(batch):
            raise ProviderError(
                f"Mistral returned {len(batch_embeddings)} embeddings but expected {len(batch)}"
            )
        if batch_embeddings and len(batch_embeddings[0]) != expected_dims:
            raise ProviderError(
                f"Mistral embedding dimensions mismatch: "
                f"got {len(batch_embeddings[0])}, expected {expected_dims}.",
                retryable=False,
            )
        return batch_embeddings

    def _count_tokens_for_texts(self, texts: List[str]) -> int:
        """Count tokens for a list of texts."""
        if self.embedding_tokenizer:
            return sum(self.count_tokens(text, self.embedding_tokenizer) for text in texts)
        return sum(len(text) // 4 for text in texts)  # Fallback estimate

    async def _embed_with_token_limits(
        self, texts: List[str], expected_dims: int
    ) -> List[List[float]]:
        """Embed texts, splitting if token limits exceeded."""
        if not texts:
            return []

        total_tokens = self._count_tokens_for_texts(texts)

        if len(texts) == 1 and total_tokens > self.MAX_TOKENS_PER_REQUEST:
            self.ctx.logger.warning(
                f"[EMBED] Skipping text with {total_tokens} tokens "
                f"(max {self.MAX_TOKENS_PER_REQUEST})"
            )
            return [[0.0] * expected_dims]

        if total_tokens > self.MAX_TOKENS_PER_REQUEST:
            self.ctx.logger.debug(
                f"[EMBED] Batch exceeds {self.MAX_TOKENS_PER_REQUEST} tokens, splitting"
            )
            mid = len(texts) // 2
            first_half = await self._embed_with_token_limits(texts[:mid], expected_dims)
            second_half = await self._embed_with_token_limits(texts[mid:], expected_dims)
            return first_half + second_half

        results: List[List[float]] = []
        for batch_start in range(0, len(texts), self.MAX_EMBEDDING_BATCH_SIZE):
            batch = texts[batch_start : batch_start + self.MAX_EMBEDDING_BATCH_SIZE]
            results.extend(await self._embed_single_batch(batch, expected_dims))
        return results

    async def embed(self, texts: List[str], dimensions: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings using Mistral."""
        expected_dims = self._validate_embed_inputs(texts, dimensions)

        if self._mock_embeddings:
            return self._mock_embed_many(texts, expected_dims)

        embeddings = await self._embed_with_token_limits(texts, expected_dims)

        if len(embeddings) != len(texts):
            raise ProviderError(
                f"Embedding count mismatch: got {len(embeddings)} for {len(texts)} texts"
            )
        return embeddings

    @staticmethod
    def _mock_embed_many(texts: List[str], dimensions: Optional[int]) -> List[List[float]]:
        """Return deterministic mock embeddings without external API calls."""
        if not dimensions:
            raise ProviderError("Mock Mistral embeddings require explicit dimensions")

        embeddings: List[List[float]] = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
            rng = random.Random(seed)
            embeddings.append([rng.uniform(-1.0, 1.0) for _ in range(dimensions)])

        return embeddings

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Rerank documents using Mistral structured output."""
        from airweave.search.prompts import RERANKING_SYSTEM_PROMPT

        if not self.model_spec.rerank_model:
            raise RuntimeError("Rerank model not configured for Mistral provider")

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
            raise ProviderError("Mistral returned empty rankings")

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
                "Ensure tokenizer is configured in defaults.yml for Mistral rerank model."
            )

        if not self.model_spec.rerank_model or not self.model_spec.rerank_model.context_window:
            raise RuntimeError("Context window required for Mistral reranking")

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
