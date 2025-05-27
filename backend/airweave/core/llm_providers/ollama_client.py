"""Ollama CLient to handle Ollama request."""

from typing import AsyncGenerator, Dict, List

import httpx
from openai.types.chat import ChatCompletionChunk

from .base import BaseLLMClient


class OllamaClient(BaseLLMClient):
    """Client for Ollama."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        """Client Initialised for Ollama."""
        self.base_url = base_url.rstrip("/")

    async def create_completion(
        self, messages: List[Dict], model: str, stream: bool = False, **kwargs
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Call Ollama local server to generate completion."""
        import json

        prompt = "\n".join([msg["content"] for msg in messages if msg["role"] != "system"])

        payload = {"model": model, "prompt": prompt, "stream": stream}

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload, timeout=60
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if data.get("done"):
                                return
                            content = data.get("response", "")
                            if content:
                                yield ChatCompletionChunk.model_construct(
                                    choices=[
                                        {
                                            "delta": {"content": content},
                                            "finish_reason": None,
                                            "index": 0,
                                        }
                                    ]
                                )
                        except Exception as parse_error:
                            raise RuntimeError(
                                f"Failed to parse Ollama response line: {line}"
                            ) from parse_error

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama returned an error: {e.response.text}") from e
        except httpx.RequestError as e:
            raise RuntimeError(
                "Ollama server is unreachable. Please ensure Ollama is running locally at http://localhost:11434"
            ) from e
