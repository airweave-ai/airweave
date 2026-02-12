"""Fallback OCR provider with circuit breaker integration.

Tries OCR providers in order, skipping circuit-broken ones. Satisfies
the OcrProvider protocol — drop-in replacement anywhere a single
provider is accepted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from airweave.core.logging import logger

if TYPE_CHECKING:
    from airweave.core.protocols import CircuitBreaker, OcrProvider


class FallbackOcrProvider:
    """Tries OCR providers in priority order, skipping circuit-broken ones.

    Wraps multiple OcrProvider implementations behind a single OcrProvider
    interface. Uses a CircuitBreaker to track which providers are healthy.

    Usage::

        ocr = FallbackOcrProvider(
            providers=[
                ("mistral-ocr", MistralOcrAdapter()),
                ("google-document-ai", GoogleDocAIOcrAdapter()),
            ],
            circuit_breaker=InMemoryCircuitBreaker(cooldown_seconds=120),
        )
        results = await ocr.convert_batch(["/tmp/doc.pdf"])
    """

    def __init__(
        self,
        providers: List[Tuple[str, "OcrProvider"]],
        circuit_breaker: "CircuitBreaker",
    ) -> None:
        """Initialize the fallback provider.

        Args:
            providers: Ordered list of (provider_key, provider) pairs.
                Tried first-to-last; first available wins.
            circuit_breaker: Tracks provider health and cooldowns.
        """
        if not providers:
            raise ValueError("At least one OCR provider is required")
        self._providers = providers
        self._cb = circuit_breaker

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown, trying providers in order.

        Skips circuit-broken providers. On failure, records the failure
        and tries the next provider. If all providers are exhausted,
        returns None for every file.

        Args:
            file_paths: Local file paths to convert.

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on failure).
        """
        for provider_key, provider in self._providers:
            if not await self._cb.is_available(provider_key):
                logger.info(f"[FallbackOCR] Skipping '{provider_key}' (circuit-broken)")
                continue

            try:
                results = await provider.convert_batch(file_paths)
                await self._cb.record_success(provider_key)
                return results
            except Exception as exc:
                await self._cb.record_failure(provider_key)
                logger.warning(
                    f"[FallbackOCR] '{provider_key}' failed ({exc}), trying next provider"
                )

        logger.error("[FallbackOCR] All OCR providers unavailable or failed")
        return {path: None for path in file_paths}
