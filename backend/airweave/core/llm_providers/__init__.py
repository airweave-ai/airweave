"""LLM Provider initializer to get LLM client."""

from airweave.core.config import settings

from .ollama_client import OllamaClient
from .openai_client import OpenAIClient

# from .base import BaseLLMClient


def get_llm_client():
    """Get LLM Clients for selected Options."""
    if settings.LLM_PROVIDER.lower() == "ollama":
        return OllamaClient(base_url=settings.OLLAMA_BASE_URL)
    elif settings.LLM_PROVIDER.lower() == "openai":
        return OpenAIClient(api_key=settings.OPENAI_API_KEY)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")
