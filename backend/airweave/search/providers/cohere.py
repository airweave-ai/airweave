"""Cohere provider implementation.

Supports reranking using Cohere's specialized rerank API.
Does not support text generation, structured output, or embeddings.
"""

from typing import Any, Dict, List, Optional

try:
    import cohere
except ImportError:
    cohere = None

from pydantic import BaseModel
from tiktoken import Encoding

from airweave.api.context import ApiContext

from ._base import BaseProvider, ProviderError
from .schemas import ProviderModelSpec


class CohereProvider(BaseProvider):
    """Cohere LLM provider."""

    def __init__(self, api_key: str, model_spec: ProviderModelSpec, ctx: ApiContext) -> None:
        """Initialize Cohere provider with model specs from defaults.yml."""
        super().__init__(api_key, model_spec, ctx)

        if cohere is None:
            raise ImportError("Cohere package not installed. Install with: pip install cohere")

        try:
            self.client = cohere.AsyncClientV2(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Cohere client: {e}") from e

        self.ctx.logger.debug(f"[CohereProvider] Initialized with model spec: {model_spec}")

        self.rerank_tokenizer: Optional[Encoding] = None

        if model_spec.rerank_model and model_spec.rerank_model.tokenizer:
            self.rerank_tokenizer = self._load_tokenizer(
                model_spec.rerank_model.tokenizer, "rerank"
            )

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Not supported by Cohere."""
        raise NotImplementedError("Cohere does not support text generation")

    async def structured_output(
        self, messages: List[Dict[str, str]], schema: type[BaseModel]
    ) -> BaseModel:
        """Not supported by Cohere."""
        raise NotImplementedError("Cohere does not support structured output")

    async def embed(self, texts: List[str], dimensions: Optional[int] = None) -> List[List[float]]:
        """Not supported by Cohere."""
        raise NotImplementedError("Cohere does not support embeddings")

    async def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:  # noqa: C901
        """Rerank documents using Cohere Rerank API."""
        if not self.model_spec.rerank_model:
            raise RuntimeError("Rerank model not configured for Cohere provider")

        if not documents:
            raise ValueError("Cannot rerank empty document list")

        if top_n < 1:
            raise ValueError(f"top_n must be >= 1, got {top_n}")

        # Validate required Cohere-specific limits are configured
        if not self.model_spec.rerank_model.max_tokens_per_doc:
            raise ValueError("max_tokens_per_doc must be configured for Cohere rerank model")

        if not self.model_spec.rerank_model.max_documents:
            raise ValueError("max_documents must be configured for Cohere rerank model")

        max_tokens_per_doc = self.model_spec.rerank_model.max_tokens_per_doc
        max_documents = self.model_spec.rerank_model.max_documents

        # Validate document token counts before sending
        for i, doc in enumerate(documents):
            token_count = self.count_tokens(doc, self.rerank_tokenizer)
            if token_count > max_tokens_per_doc:
                raise ValueError(
                    f"Document at index {i} has ~{token_count} tokens, "
                    f"exceeds Cohere limit of {max_tokens_per_doc}. "
                    f"Operation must truncate documents before calling rerank."
                )

        # Limit documents to API maximum
        if len(documents) > max_documents:
            raise ValueError(
                f"Document list has {len(documents)} documents, "
                f"exceeds Cohere limit of {max_documents}. "
                f"Reduce candidates before calling rerank."
            )

        try:
            response = await self.client.rerank(
                model=self.model_spec.rerank_model.name,
                query=query,
                documents=documents,
                top_n=top_n,
                max_tokens_per_doc=max_tokens_per_doc,
            )
        except Exception as e:
            raise RuntimeError(f"Cohere rerank API call failed: {e}") from e

        if not response.results:
            raise ProviderError("Cohere returned empty rerank results")

        return [
            {"index": result.index, "relevance_score": result.relevance_score}
            for result in response.results
        ]
