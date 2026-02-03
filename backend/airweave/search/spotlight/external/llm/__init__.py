"""LLM integrations for spotlight search."""

from airweave.search.spotlight.config import LLMModel, LLMProvider
from airweave.search.spotlight.external.llm.interface import SpotlightLLMInterface
from airweave.search.spotlight.external.llm.registry import (
    LLMModelSpec,
    ReasoningConfig,
    get_available_models,
    get_model_spec,
)

__all__ = [
    "SpotlightLLMInterface",
    "LLMProvider",
    "LLMModel",
    "LLMModelSpec",
    "ReasoningConfig",
    "get_model_spec",
    "get_available_models",
]
