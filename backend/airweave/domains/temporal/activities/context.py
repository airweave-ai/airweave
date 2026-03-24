"""Activity context builder — shared boilerplate for Temporal activity payloads."""

from typing import Any, Dict
from uuid import UUID

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.logging import logger


async def build_activity_context(ctx_dict: Dict[str, Any], **log_dimensions: Any) -> BaseContext:
    """Build a BaseContext from a serialized Temporal activity payload.

    Args:
        ctx_dict: Serialized context dict. Uses ``"organization"`` if present,
            otherwise falls back to fetching from DB via ``"organization_id"``.
            This fallback handles schedules created before the ``"organization"``
            key was added to ``to_serializable_dict()``.
        **log_dimensions: Extra dimensions to bind to the logger
            (e.g. ``sync_id="abc"``, ``sync_job_id="def"``).

    Returns:
        A ready-to-use BaseContext with organization and enriched logger.
    """
    if "organization" in ctx_dict:
        organization = schemas.Organization(**ctx_dict["organization"])
    else:
        org_id = ctx_dict.get("organization_id")
        if not org_id:
            raise ValueError("ctx_dict has neither 'organization' nor 'organization_id'")
        logger.info(f"Fetching organization {org_id} from DB (legacy ctx_dict format)")
        organization = await _fetch_organization(UUID(org_id))

    ctx = BaseContext(organization=organization)
    if log_dimensions:
        ctx.logger = ctx.logger.with_context(**log_dimensions)
    return ctx


async def _fetch_organization(org_id: UUID) -> schemas.Organization:
    """Fetch an enriched Organization schema from DB by ID."""
    from airweave.crud import crud
    from airweave.db.session import get_db_context

    async with get_db_context() as db:
        org = await crud.organization.get(db, org_id, skip_access_validation=True, enrich=True)
        if isinstance(org, schemas.Organization):
            return org
        return schemas.Organization.model_validate(org, from_attributes=True)
