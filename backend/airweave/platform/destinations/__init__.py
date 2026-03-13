"""Destinations module.

Contains destination adapters and base classes for syncing data to various stores.

Key Classes:
- BaseDestination: Abstract base class for all destinations
- VectorDBDestination: Base class for vector database destinations
"""

from ._base import BaseDestination, VectorDBDestination

__all__ = [
    "BaseDestination",
    "VectorDBDestination",
]
