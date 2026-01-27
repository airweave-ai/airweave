"""OpenAI clients for agentic search.

This module provides specialized OpenAI clients for the agentic search loop:

- StructuredOutputClient: Reasoning models (gpt-5.2, etc.) with structured output
- AgenticEmbedder: Query embedding (dense 3072-dim + sparse BM25)
"""

from airweave.search.agentic_search.openai.embedding import (
    AgenticEmbedder,
    QueryEmbeddings,
)
from airweave.search.agentic_search.openai.structured_output import (
    ReasoningEffort,
    StructuredOutputClient,
)

__all__ = [
    "StructuredOutputClient",
    "ReasoningEffort",
    "AgenticEmbedder",
    "QueryEmbeddings",
]
