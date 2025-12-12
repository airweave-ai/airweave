"""OpenAI provider implementation.

Supports text generation, structured output, embeddings, and reranking.
Most complete provider with all capabilities.
Supports both standard OpenAI API and Azure OpenAI endpoints.
"""

from typing import Any, Dict, List, Optional

from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel
from tiktoken import Encoding

from airweave.api.context import ApiContext

from ._base import BaseProvider, ProviderError
from .schemas import ProviderModelSpec


class OpenAIProvider(BaseProvider):
    """OpenAI LLM provider.

    Supports both:
    - Standard OpenAI API (api.openai.com)
    - Azure OpenAI Service (*.openai.azure.com)

    For Azure OpenAI, provide azure_endpoint, azure_api_version, and deployment names.
    """

    MAX_COMPLETION_TOKENS = 10000
    MAX_STRUCTURED_OUTPUT_TOKENS = 20000
    MAX_EMBEDDING_BATCH_SIZE = 100
    RERANK_SAFETY_TOKENS = 1500

    TIMEOUT = 1200.0
    MAX_RETRIES = 2

    def __init__(
        self,
        api_key: str,
        model_spec: ProviderModelSpec,
        ctx: ApiContext,
        azure_endpoint: Optional[str] = None,
        azure_api_version: Optional[str] = None,
        azure_embedding_deployment: Optional[str] = None,
        azure_llm_deployment: Optional[str] = None,
    ) -> None:
        """Initialize OpenAI provider with model specs from defaults.yml.

        Args:
            api_key: OpenAI or Azure OpenAI API key
            model_spec: Model specification from defaults.yml
            ctx: API context for logging
            azure_endpoint: Optional Azure OpenAI endpoint (e.g., https://your-resource.openai.azure.com/)
            azure_api_version: Optional Azure OpenAI API version (e.g., 2024-02-01)
            azure_embedding_deployment: Optional Azure deployment name for embeddings
            azure_llm_deployment: Optional Azure deployment name for LLM operations
        """
        super().__init__(api_key, model_spec, ctx)

        self.is_azure = azure_endpoint is not None
        self.azure_embedding_deployment = azure_embedding_deployment
        self.azure_llm_deployment = azure_llm_deployment

        try:
            if self.is_azure:
                # Azure OpenAI client
                if not azure_api_version:
                    raise ValueError("azure_api_version is required for Azure OpenAI")

                # Validate that at least one deployment is configured
                if model_spec.embedding_model and not azure_embedding_deployment:
                    raise ValueError(
                        "azure_embedding_deployment is required when using Azure OpenAI for embeddings. "
                        "Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT in your environment."
                    )

                if model_spec.llm_model and not azure_llm_deployment:
                    raise ValueError(
                        "azure_llm_deployment is required when using Azure OpenAI for LLM operations. "
                        "Set AZURE_OPENAI_LLM_DEPLOYMENT in your environment."
                    )

                self.client = AsyncAzureOpenAI(
                    api_key=api_key,
                    azure_endpoint=azure_endpoint,
                    api_version=azure_api_version,
                    timeout=self.TIMEOUT,
                    max_retries=self.MAX_RETRIES,
                )
                self.ctx.logger.info(
                    f"[OpenAIProvider] Initialized Azure OpenAI client: {azure_endpoint}, "
                    f"API version: {azure_api_version}"
                )
            else:
                # Standard OpenAI client
                self.client = AsyncOpenAI(
                    api_key=api_key, timeout=self.TIMEOUT, max_retries=self.MAX_RETRIES
                )
                self.ctx.logger.info("[OpenAIProvider] Initialized standard OpenAI client")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}") from e

        # Log which embedding model we're using (if any)
        if model_spec.embedding_model:
            if self.is_azure and azure_embedding_deployment:
                self.ctx.logger.info(
                    f"[OpenAIProvider] Using Azure embedding deployment: {azure_embedding_deployment} "
                    f"({model_spec.embedding_model.dimensions}-dim)"
                )
            else:
                self.ctx.logger.info(
                    f"[OpenAIProvider] Using embedding model: {model_spec.embedding_model.name} "
                    f"({model_spec.embedding_model.dimensions}-dim)"
                )

        self.ctx.logger.debug(f"[OpenAIProvider] Initialized with model spec: {model_spec}")

        self.llm_tokenizer: Optional[Encoding] = None
        self.embedding_tokenizer: Optional[Encoding] = None
        self.rerank_tokenizer: Optional[Encoding] = None

        if model_spec.llm_model:
            self.llm_tokenizer = self._load_tokenizer(model_spec.llm_model.tokenizer, "llm")

        if model_spec.embedding_model:
            self.embedding_tokenizer = self._load_tokenizer(
                model_spec.embedding_model.tokenizer, "embedding"
            )

        if model_spec.rerank_model and model_spec.rerank_model.tokenizer:
            self.rerank_tokenizer = self._load_tokenizer(
                model_spec.rerank_model.tokenizer, "rerank"
            )

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Generate text completion using OpenAI."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for OpenAI provider")

        if not messages:
            raise ValueError("Cannot generate completion with empty messages")

        # Use Azure deployment name if available, otherwise use model name
        model_name = (
            self.azure_llm_deployment if self.is_azure and self.azure_llm_deployment
            else self.model_spec.llm_model.name
        )

        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_completion_tokens=self.MAX_COMPLETION_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI completion API call failed: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise ProviderError("OpenAI returned empty completion content")

        return content

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Generate structured output using OpenAI Responses API."""
        if not self.model_spec.llm_model:
            raise RuntimeError("LLM model not configured for OpenAI provider")

        if not messages:
            raise ValueError("Cannot generate structured output with empty messages")

        if not schema:
            raise ValueError("Schema is required for structured output")

        # Use Azure deployment name if available, otherwise use model name
        model_name = (
            self.azure_llm_deployment if self.is_azure and self.azure_llm_deployment
            else self.model_spec.llm_model.name
        )

        try:
            response = await self.client.responses.parse(
                model=model_name,
                input=messages,
                text_format=schema,
                max_output_tokens=self.MAX_STRUCTURED_OUTPUT_TOKENS,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI structured output API call failed: {e}") from e

        parsed = response.output_parsed
        if not parsed:
            raise ProviderError("OpenAI returned empty structured output")

        return parsed

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with batching and validation."""
        if not self.model_spec.embedding_model:
            raise RuntimeError("Embedding model not configured for OpenAI provider")

        if not texts:
            raise ValueError("Cannot embed empty text list")

        self._validate_embed_inputs(texts)
        return await self._process_embeddings(texts)

    def _validate_embed_inputs(self, texts: List[str]) -> None:
        """Validate texts for embedding."""
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} is empty")

        max_tokens = self.model_spec.embedding_model.max_tokens
        if not max_tokens:
            raise ValueError("Max tokens not configured for embedding model")

        if not self.embedding_tokenizer:
            raise RuntimeError("Embedding tokenizer not initialized for OpenAI provider")

        for i, text in enumerate(texts):
            token_count = self.count_tokens(text, self.embedding_tokenizer)
            if token_count > max_tokens:
                raise ValueError(
                    f"Text at index {i} has {token_count} tokens, exceeds max of {max_tokens}"
                )

    async def _process_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Process embeddings in batches."""
        all_embeddings = []

        for batch_start in range(0, len(texts), self.MAX_EMBEDDING_BATCH_SIZE):
            batch = texts[batch_start : batch_start + self.MAX_EMBEDDING_BATCH_SIZE]
            batch_result = await self._embed_batch(batch, batch_start)
            all_embeddings.extend(batch_result)

        if len(all_embeddings) != len(texts):
            raise ProviderError(
                f"Embedding count mismatch: got {len(all_embeddings)} for {len(texts)} texts"
            )

        return all_embeddings

    async def _embed_batch(self, batch: List[str], batch_start: int) -> List[List[float]]:
        """Embed a single batch with validation."""
        # Use Azure deployment name if available, otherwise use model name
        model_name = (
            self.azure_embedding_deployment if self.is_azure and self.azure_embedding_deployment
            else self.model_spec.embedding_model.name
        )

        try:
            response = await self.client.embeddings.create(
                input=batch,
                model=model_name,
            )
        except Exception as e:
            raise RuntimeError(
                f"OpenAI embeddings API call failed at index {batch_start}: {e}"
            ) from e

        if not response.data:
            raise ProviderError(f"OpenAI returned no embeddings for batch at {batch_start}")

        if len(response.data) != len(batch):
            raise ProviderError(
                f"OpenAI returned {len(response.data)} embeddings but expected {len(batch)}"
            )

        return [item.embedding for item in response.data]

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        """Rerank documents using OpenAI structured output."""
        from airweave.search.prompts import RERANKING_SYSTEM_PROMPT

        if not self.model_spec.rerank_model:
            raise RuntimeError("Rerank model not configured for OpenAI provider")

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
            raise ProviderError("OpenAI returned empty rankings")

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
                "Ensure tokenizer is configured in defaults.yml for OpenAI rerank model."
            )

        if not self.model_spec.rerank_model or not self.model_spec.rerank_model.context_window:
            raise RuntimeError("Context window required for OpenAI reranking")

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
