"""OpenAI Client to handle request for OpenAI."""

from typing import AsyncGenerator, Dict, List

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from .base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI."""

    def __init__(self, api_key: str):
        """Client Initialised for OpenAI."""
        self.client = AsyncOpenAI(api_key=api_key)

    async def create_completion(
        self, messages: List[Dict], model: str, stream: bool = False, **kwargs
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Create a chat completion based on given messages."""
        return await self.client.chat.completions.create(
            model=model, messages=messages, stream=stream, **kwargs
        )
