"""LLM's client base Abstract class."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Union


class BaseLLMClient(ABC):
    """Abstract class for LLM Providers/Client."""

    @abstractmethod
    async def create_completion(
        self, messages: List[Dict], model: str, stream: bool = False, **kwargs
    ) -> Union[Dict, AsyncGenerator]:
        """Create a chat completion based on given messages."""
        pass
