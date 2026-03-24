"""Typed result objects returned by Temporal activities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CreateSyncJobResult:
    """Result of the create-sync-job activity.

    Exactly one of ``sync_job_dict``, ``orphaned``, or ``skipped`` is set.
    The workflow inspects these fields instead of grepping for magic dict keys.
    """

    sync_job_dict: dict[str, Any] | None = field(default=None)
    orphaned: bool = False
    skipped: bool = False
    reason: str = ""
    sync_id: str = ""
