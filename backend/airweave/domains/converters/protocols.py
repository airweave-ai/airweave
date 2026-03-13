"""Protocols for the converters domain."""

from __future__ import annotations

from typing import Optional, Protocol

from airweave.domains.converters._base import BaseTextConverter


class ConverterRegistryProtocol(Protocol):
    """Registry that maps file extensions to converter instances."""

    def for_extension(self, ext: str) -> Optional[BaseTextConverter]:
        """Return the converter for a given file extension, or None."""
        ...

    def for_web(self) -> BaseTextConverter:
        """Return the web converter."""
        ...
