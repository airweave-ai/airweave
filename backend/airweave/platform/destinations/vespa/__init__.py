"""Vespa destination package.

This package provides the VespaDestination for storing and searching
entities in Vespa using a chunk-as-document model.

Public API:
    VespaDestination - Main destination class for Vespa operations
"""

from airweave.platform.destinations.vespa.destination import VespaDestination

__all__ = ["VespaDestination"]
