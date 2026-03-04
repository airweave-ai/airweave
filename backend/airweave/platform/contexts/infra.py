"""Infrastructure context — compatibility shim.

Kept temporarily because sub-builders (source.py, destinations.py, tracking.py)
still accept InfraContext as a parameter. Will be removed when those builders
are refactored to accept (ctx, logger) directly.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.core.context import BaseContext
    from airweave.core.logging import ContextualLogger


@dataclass
class InfraContext:
    """Thin wrapper around (ctx, logger) for sub-builder compatibility."""

    ctx: "BaseContext"
    logger: "ContextualLogger"
