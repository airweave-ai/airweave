"""Code file to markdown converter with AI-generated summaries."""

import asyncio
import os
from typing import Dict, List

import aiofiles
from tiktoken import get_encoding

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter
from airweave.platform.rate_limiters import OpenAIRateLimiter
from airweave.platform.sync.exceptions import SyncFailureError

# ==================== CONFIGURATION ====================

# System prompt for code summarization
SUMMARY_SYSTEM_PROMPT = """You are a code documentation expert. Generate a concise 2-3 \
sentence summary of the provided code file.

Focus on:
- What the code does (purpose/functionality)
- Key classes, functions, or components
- Any notable patterns or technologies used

Keep the summary brief and semantic-search friendly. Do NOT include line-by-line \
explanations."""


# ==================== CODE CONVERTER ====================


class CodeConverter(BaseTextConverter):
    """Converts code files to markdown with AI-generated summaries.

    Uses OpenAI Responses API (gpt-5-nano) to generate concise summaries.
    Falls back to raw code if file is too large for context window.
    """

    # Token limits (gpt-5-nano)
    MAX_INPUT_TOKENS = 380_000  # Leave 20k buffer from 400k context window
    MAX_OUTPUT_TOKENS = 128_000  # Summary length

    def __init__(self):
        """Initialize converter with lazy OpenAI client and tokenizer."""
        self.rate_limiter = OpenAIRateLimiter()
        self._openai_client = None
        self._openai_initialized = False

        # Load tokenizer for gpt-5-nano
        try:
            self.tokenizer = get_encoding("cl100k_base")
        except Exception as e:
            raise SyncFailureError(f"Failed to load tokenizer: {e}")

    def _ensure_openai_client(self):
        """Ensure OpenAI client is initialized (lazy initialization).

        Raises:
            SyncFailureError: If OpenAI API key not configured or package not installed
        """
        if self._openai_initialized:
            return

        # Require OpenAI API key
        if not hasattr(settings, "OPENAI_API_KEY") or not settings.OPENAI_API_KEY:
            raise SyncFailureError("OPENAI_API_KEY required for code summarization")

        try:
            from openai import AsyncOpenAI

            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)
            self._openai_initialized = True
            logger.debug("OpenAI client initialized for code summarization")
        except ImportError:
            raise SyncFailureError("openai package required but not installed")

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self.tokenizer.encode(text))

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert code files to markdown with AI summaries.

        Args:
            file_paths: List of code file paths

        Returns:
            Dict mapping file_path -> markdown (summary + code fence)
        """
        # Ensure OpenAI client is initialized
        self._ensure_openai_client()

        logger.debug(f"Converting {len(file_paths)} code files with AI summaries...")

        results = {}
        semaphore = asyncio.Semaphore(5)  # Limit concurrent API calls

        async def _convert_one(path: str):
            async with semaphore:
                try:
                    # Read file
                    async with aiofiles.open(path, "r", encoding="utf-8", errors="ignore") as f:
                        code = await f.read()

                    if not code or not code.strip():
                        logger.warning(f"Code file {path} is empty")
                        results[path] = None
                        return

                    # Get language from extension
                    _, ext = os.path.splitext(path)
                    lang = ext.lstrip(".") if ext else ""

                    # Check token budget
                    token_count = self._count_tokens(code)

                    # Create code fence
                    code_fence = f"```{lang}\n{code}\n```"

                    # Generate summary if file fits in context window
                    if token_count <= self.MAX_INPUT_TOKENS:
                        try:
                            summary = await self._generate_summary(code, lang)
                            if summary:
                                results[path] = f"{summary}\n\n{code_fence}"
                                logger.debug(
                                    f"Generated summary for {os.path.basename(path)} "
                                    f"({token_count} tokens)"
                                )
                            else:
                                results[path] = code_fence
                        except Exception as e:
                            # Summary failed - use raw code
                            logger.warning(
                                f"Summary generation failed for {os.path.basename(path)}: {e}, "
                                f"using raw code"
                            )
                            results[path] = code_fence
                    else:
                        # File too large - skip summary
                        logger.debug(
                            f"Code file {os.path.basename(path)}: {token_count} tokens "
                            f"exceeds {self.MAX_INPUT_TOKENS} (skipping summary)"
                        )
                        results[path] = code_fence

                except Exception as e:
                    logger.error(f"Failed to process code file {path}: {e}")
                    results[path] = None

        await asyncio.gather(*[_convert_one(p) for p in file_paths], return_exceptions=True)

        successful = sum(1 for r in results.values() if r)
        logger.debug(f"Code conversion complete: {successful}/{len(file_paths)} successful")

        return results

    async def _generate_summary(self, code: str, lang: str) -> str:
        """Generate AI summary for code file using OpenAI Responses API.

        Args:
            code: Code content
            lang: Language identifier

        Returns:
            Summary text or empty string if failed
        """
        # Rate limit the API call
        await self.rate_limiter.acquire()

        try:
            response = await self._openai_client.responses.create(
                model="gpt-5-nano",
                instructions=SUMMARY_SYSTEM_PROMPT,
                input=f"```{lang}\n{code}\n```",
                max_output_tokens=self.MAX_OUTPUT_TOKENS,
                store=False,  # Don't store summaries
            )

            if hasattr(response, "output_text") and response.output_text:
                return response.output_text.strip()

            logger.warning("OpenAI returned empty summary")
            return ""

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
