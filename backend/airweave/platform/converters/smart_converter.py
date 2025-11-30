from typing import Any, Dict, List, Optional

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.converters.markitdown_converter import MarkItDownConverter
from airweave.platform.converters.mistral_converter import MistralConverter


class SmartConverter:
    """A smart converter that selects the best available conversion strategy.

    Priority:
    1. OpenAI (via MarkItDown) - Best for Vision/OCR/Complex Docs
    2. Mistral (via MistralConverter) - Good OCR
    3. Local (via MarkItDown) - Basic text extraction (fallback)
    """

    def __init__(self):
        self.openai_converter = None
        self.mistral_converter = None
        self.local_converter = None
        self._initialize_strategies()

    @property
    def openai_available(self) -> bool:
        return self.openai_converter is not None

    @property
    def mistral_available(self) -> bool:
        return self.mistral_converter is not None

    def _initialize_strategies(self):
        """Initialize available strategies based on configuration."""
        # 1. OpenAI Strategy (Best)
        if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
            try:
                # MarkItDownConverter automatically uses OpenAI if key is present in settings
                # We create a specific instance for it
                openai_converter = MarkItDownConverter()
                # Verify it actually has the client (it should, based on its __init__)
                if openai_converter._md._llm_client:
                    self.openai_converter = openai_converter
                    logger.info("SmartConverter: OpenAI strategy available")
            except Exception as e:
                logger.warning(f"SmartConverter: Failed to initialize OpenAI strategy: {e}")

        # 2. Mistral Strategy (Good)
        if hasattr(settings, "MISTRAL_API_KEY") and settings.MISTRAL_API_KEY:
            try:
                self.mistral_converter = MistralConverter()
                logger.info("SmartConverter: Mistral strategy available")
            except Exception as e:
                logger.warning(f"SmartConverter: Failed to initialize Mistral strategy: {e}")

        # 3. Local Strategy (Fallback)
        # Always available via MarkItDown (it falls back to local if no LLM client)
        try:
            self.local_converter = MarkItDownConverter()
            logger.info("SmartConverter: Local strategy available")
        except Exception as e:
            logger.error(f"SmartConverter: Failed to initialize Local strategy: {e}")

    def _get_converter(self, preferred_model: Optional[str] = None) -> Any:
        """Determine which converter to use based on preference and availability."""
        
        # 1. Honor preference if valid and available
        if preferred_model == "openai" and self.openai_available:
            return self.openai_converter
        if preferred_model == "mistral" and self.mistral_available:
            return self.mistral_converter
        if preferred_model == "local":
            return self.local_converter

        # 2. Fallback to default priority logic
        if self.openai_available:
            return self.openai_converter
        elif self.mistral_available:
            return self.mistral_converter
        else:
            # Fallback to local if nothing else is available
            return self.local_converter

    async def convert(self, file_path: str, preferred_model: Optional[str] = None) -> str:
        """Convert a single file using the best available or preferred strategy.

        Args:
            file_path: Path to the file to convert.
            preferred_model: Optional preferred model ("openai", "mistral", "local").

        Returns:
            Converted text content.
        """
        converter = self._get_converter(preferred_model)
        if not converter:
             raise RuntimeError(f"No suitable converter found (preferred: {preferred_model})")

        # Handle different converter interfaces
        if hasattr(converter, "convert"):
            return await converter.convert(file_path)
        elif hasattr(converter, "convert_batch"):
            results = await converter.convert_batch([file_path])
            if results and results.get(file_path):
                return results[file_path]
            raise ValueError(f"Converter returned empty result for {file_path}")
        else:
            raise NotImplementedError(f"Converter {converter.__class__.__name__} has no compatible convert method")

    async def convert_batch(self, file_paths: List[str], preferred_model: Optional[str] = None) -> Dict[str, str]:
        """Convert a batch of files using the best available or preferred strategy.

        Args:
            file_paths: List of file paths to convert.
            preferred_model: Optional preferred model ("openai", "mistral", "local").

        Returns:
            Dictionary mapping file paths to converted text content.
        """
        converter = self._get_converter(preferred_model)
        if not converter:
             raise RuntimeError(f"No suitable converter found (preferred: {preferred_model})")

        if hasattr(converter, "convert_batch"):
            return await converter.convert_batch(file_paths)
        else:
            # Fallback to loop if converter doesn't support batching
            results = {}
            for path in file_paths:
                try:
                    results[path] = await self.convert(path, preferred_model)
                except Exception as e:
                    logger.warning(f"Failed to convert {path}: {e}")
            return results
