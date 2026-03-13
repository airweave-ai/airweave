"""Source context — compatibility shim.

Kept temporarily because SourceContextBuilder returns SourceContext.
Will be removed when SourceContextBuilder is inlined into SyncContextBuilder.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.platform.sources._base import BaseSource
    from airweave.domains.sync_pipeline.cursor import SyncCursor


@dataclass
class SourceContext:
    """Source pipeline components."""

    source: "BaseSource"
    cursor: "SyncCursor"
