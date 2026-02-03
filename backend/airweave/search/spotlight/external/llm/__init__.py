"""LLM integrations for spotlight search."""

from airweave.search.spotlight.config import LLMProvider, ModelName
from airweave.search.spotlight.external.llm.interface import SpotlightLLMInterface
from airweave.search.spotlight.external.llm.registry import (
    ModelSpec,
    ReasoningConfig,
    get_available_models,
    get_model_spec,
)

__all__ = [
    "SpotlightLLMInterface",
    "LLMProvider",
    "ModelName",
    "ModelSpec",
    "ReasoningConfig",
    "get_model_spec",
    "get_available_models",
]
