"""Infrastructure context."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.api.context import ApiContext
    from airweave.core.logging import ContextualLogger


@dataclass
class InfraContext:
    """Core infrastructure needed by all operations.

    Contains API context and logger. Other contexts and builders
    can extract what they need from this.

    Attributes:
        ctx: API context for auth and audit
        logger: Contextual logger with operation metadata
    """

    ctx: "ApiContext"
    logger: "ContextualLogger"
