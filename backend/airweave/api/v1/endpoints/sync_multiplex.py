"""Endpoints for sync multiplexing (destination migrations).

Enables blue-green deployments for vector DB migrations:
- Fork: Add shadow destination + optionally replay from ARF
- Switch: Promote shadow to active
- List: Show all destinations with roles
- Resync: Force full sync from source to refresh ARF

Feature-gated: Requires SYNC_MULTIPLEXER feature flag enabled for the organization.
"""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.shared_models import FeatureFlag
from airweave.platform.sync.multiplex.multiplexer import SyncMultiplexer

router = TrailingSlashRouter()


def _require_multiplexer_feature(ctx: ApiContext) -> None:
    """Check if organization has multiplexer feature enabled.

    Args:
        ctx: API context

    Raises:
        HTTPException: If feature not enabled
    """
    if not ctx.has_feature(FeatureFlag.SYNC_MULTIPLEXER):
        raise HTTPException(
            status_code=403,
            detail="Sync multiplexer feature is not enabled for this organization",
        )


@router.get(
    "/{sync_id}/destinations",
    response_model=List[schemas.DestinationSlotInfo],
    summary="List destination slots",
    description="List all destinations for a sync with their roles (active/shadow/deprecated).",
)
async def list_destinations(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.DestinationSlotInfo]:
    """List all destination slots for a sync.

    Returns slots sorted by role: ACTIVE first, then SHADOW, then DEPRECATED.
    """
    _require_multiplexer_feature(ctx)
    multiplexer = SyncMultiplexer(db, ctx, ctx.logger)
    return await multiplexer.list_destinations(sync_id)


@router.post(
    "/{sync_id}/destinations/fork",
    response_model=schemas.ForkDestinationResponse,
    summary="Fork a new destination",
    description="Add a shadow destination for migration testing. Optionally replay from ARF store.",
)
async def fork_destination(
    sync_id: UUID,
    request: schemas.ForkDestinationRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ForkDestinationResponse:
    """Fork a new shadow destination.

    Creates a new destination slot with SHADOW role. If replay_from_arf is True,
    entities will be replayed from the ARF store to populate the new destination.

    Args:
        sync_id: Sync ID to fork destination for
        request: Fork request with destination connection ID and replay flag
        db: Database session
        ctx: API context

    Returns:
        ForkDestinationResponse with slot and optional replay job info
    """
    _require_multiplexer_feature(ctx)
    multiplexer = SyncMultiplexer(db, ctx, ctx.logger)
    slot, replay_job = await multiplexer.fork(
        sync_id=sync_id,
        destination_connection_id=request.destination_connection_id,
        replay_from_arf=request.replay_from_arf,
    )

    slot_schema = schemas.SyncConnectionSchema(
        id=slot.id,
        sync_id=slot.sync_id,
        connection_id=slot.connection_id,
        role=slot.role,
        created_at=slot.created_at,
        modified_at=slot.modified_at,
    )

    return schemas.ForkDestinationResponse(
        slot=slot_schema,
        replay_job_id=replay_job.id if replay_job else None,
        replay_job_status=replay_job.status.value if replay_job else None,
    )


@router.post(
    "/{sync_id}/destinations/{slot_id}/switch",
    response_model=schemas.SwitchDestinationResponse,
    summary="Switch active destination",
    description="Promote a shadow destination to active. The current active becomes deprecated.",
)
async def switch_destination(
    sync_id: UUID,
    slot_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SwitchDestinationResponse:
    """Switch the active destination.

    Promotes the specified shadow slot to ACTIVE and demotes the current
    ACTIVE slot to DEPRECATED.

    Args:
        sync_id: Sync ID
        slot_id: Slot ID to promote to active
        db: Database session
        ctx: API context

    Returns:
        Switch response with new and previous active slot IDs
    """
    _require_multiplexer_feature(ctx)
    multiplexer = SyncMultiplexer(db, ctx, ctx.logger)
    return await multiplexer.switch(sync_id=sync_id, new_active_slot_id=slot_id)


@router.post(
    "/{sync_id}/resync",
    response_model=schemas.SyncJob,
    summary="Resync from source",
    description="Force a full sync from the source to refresh the ARF store.",
)
async def resync_from_source(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SyncJob:
    """Force full sync from source to refresh ARF.

    Triggers a full sync (ignoring cursor) to ensure the ARF store is up-to-date
    before forking to a new destination.

    Args:
        sync_id: Sync ID
        db: Database session
        ctx: API context

    Returns:
        SyncJob for tracking progress
    """
    _require_multiplexer_feature(ctx)
    multiplexer = SyncMultiplexer(db, ctx, ctx.logger)
    return await multiplexer.resync_from_source(sync_id=sync_id)


@router.get(
    "/{sync_id}/destinations/active",
    response_model=schemas.DestinationSlotInfo,
    summary="Get active destination",
    description="Get the currently active destination for a sync.",
)
async def get_active_destination(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.DestinationSlotInfo:
    """Get the active destination slot.

    Args:
        sync_id: Sync ID
        db: Database session
        ctx: API context

    Returns:
        Active destination info

    Raises:
        HTTPException: If no active destination found
    """
    _require_multiplexer_feature(ctx)
    multiplexer = SyncMultiplexer(db, ctx, ctx.logger)
    active = await multiplexer.get_active_destination(sync_id)
    if not active:
        raise HTTPException(
            status_code=404,
            detail=f"No active destination found for sync {sync_id}",
        )
    return active
