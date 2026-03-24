"""Activity context builder — shared boilerplate for Temporal activity payloads."""

from typing import Any, Dict

from airweave import schemas
from airweave.core.context import BaseContext


def build_activity_context(ctx_dict: Dict[str, Any], **log_dimensions: Any) -> BaseContext:
    """Build a BaseContext from a serialized Temporal activity payload.

    Args:
        ctx_dict: Serialized context dict (must contain ``"organization"`` key).
        **log_dimensions: Extra dimensions to bind to the logger
            (e.g. ``sync_id="abc"``, ``sync_job_id="def"``).

    Returns:
        A ready-to-use BaseContext with organization and enriched logger.
    """
    organization = schemas.Organization(**ctx_dict["organization"])
    ctx = BaseContext(organization=organization)
    if log_dimensions:
        ctx.logger = ctx.logger.with_context(**log_dimensions)
    return ctx
